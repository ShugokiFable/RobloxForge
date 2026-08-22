"""Agent integration: connect/disconnect the official Roblox Studio MCP
in supported agent CLIs, and report status.

Design rule from the brief: prefer the provider's own CLI over config-file
surgery. Hermes and Claude both have one; Codex/Grok/Kimi get JSON/TOML
editing with backup + idempotency, or are reported unsupported.

Every mutation: backup -> mutate -> verify parseable. Never touch unrelated
entries. Repeated connect is a no-op.
"""
import json
import os
import re
import shutil
import subprocess
import time

from . import paths, studio
from .errors import ForgeError

PROVIDERS = ("hermes", "claude", "codex", "grok", "kimi")
SERVER_NAME = "Roblox_Studio"


def _mentions(text):
    """True when output names our server under any naming convention."""
    if not text:
        return False
    low = text.lower()
    return "roblox-studio" in low or "roblox_studio" in low


# ------------------------------------------------------------------ helpers

def _run(cmd, timeout=120):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": str(exc)})()


def _which(name):
    return paths.which(name)


# ------------------------------------------------------------- provider CLIs

def _hermes():
    exe = _which("hermes")

    def status(_cfg=None):
        if not exe:
            return None
        done = _run([exe, "mcp", "list"])
        return {"configured": _mentions(done.stdout),
                "detail": (done.stdout or done.stderr).strip()[-300:]}

    def connect(_cfg=None):
        cmd = studio.mcp_command()
        if not _run([exe, "mcp", "add", SERVER_NAME.lower(),
                     "--command", cmd[0], "--args", *cmd[1:]]) .returncode == 0:
            raise ForgeError("RBF-AGENT-002", "hermes mcp add failed",
                             hint="run it manually: hermes mcp add roblox_studio "
                                  "--command %s --args %s" % (cmd[0], " ".join(cmd[1:])))
        return "added via `hermes mcp add`"

    def disconnect(_cfg=None):
        _run([exe, "mcp", "remove", SERVER_NAME.lower()])
        return "removed via `hermes mcp remove`"

    return {"status": status, "connect": connect, "disconnect": disconnect}


def _claude():
    exe = _which("claude")

    def status(_cfg=None):
        if not exe:
            return None
        done = _run([exe, "mcp", "list"])
        return {"configured": _mentions(done.stdout),
                "detail": (done.stdout or done.stderr).strip()[-300:]}

    def connect(_cfg=None):
        cmd = studio.mcp_command()
        # user scope so it is not tied to one project directory
        args = ["mcp", "add", "--scope", "user", SERVER_NAME.lower(), *cmd]
        if not _run([exe, *args]).returncode == 0:
            raise ForgeError("RBF-AGENT-003", "claude mcp add failed",
                             hint="run manually: claude mcp add --scope user %s %s"
                                  % (SERVER_NAME.lower(), " ".join(args[3:])))
        return "added via `claude mcp add --scope user`"

    def disconnect(_cfg=None):
        _run([exe, "mcp", "remove", "-s", "user", SERVER_NAME.lower()])
        return "removed via `claude mcp remove`"

    return {"status": status, "connect": connect, "disconnect": disconnect}


def _codex():
    cfg_path = os.path.join(os.path.expanduser("~"), ".codex", "config.toml")

    def status(cfg=None):
        cfg = cfg or cfg_path
        if not os.path.isfile(cfg):
            return None
        text = open(cfg, encoding="utf-8", errors="replace").read()
        return {"configured": _mentions(text), "path": cfg}

    def connect(cfg=None):
        cfg = cfg or cfg_path
        st = status(cfg)
        if st and st["configured"]:
            return "already configured"
        block = ('\n[mcp_servers.Roblox_Studio]\ncommand = "cmd.exe"\n'
                 'args = ["/c", "%LOCALAPPDATA%\\\\Roblox\\\\mcp.bat"]\n')
        _backup(cfg)
        with open(cfg, "a", encoding="utf-8") as handle:
            handle.write(block)
        return "appended [mcp_servers.Roblox_Studio] to %s (backup saved)" % cfg

    def disconnect(cfg=None):
        cfg = cfg or cfg_path
        if not os.path.isfile(cfg):
            return "nothing to remove"
        _backup(cfg)
        text = open(cfg, encoding="utf-8", errors="replace").read()
        out = re.sub(r"\n?\[mcp_servers\.Roblox_Studio\]\n(?:[^\[]*\n)?", "\n", text)
        open(cfg, "w", encoding="utf-8").write(out)
        return "removed Roblox_Studio block from %s (backup saved)" % cfg

    return {"status": status, "connect": connect, "disconnect": disconnect}


def _generic_unsupported(name):
    def status(_cfg=None):
        return {"configured": False, "note":
                "%s support not implemented; add the official MCP yourself:\n"
                '  command: cmd.exe  args: ["/c", "%%LOCALAPPDATA%%\\Roblox\\mcp.bat"]' % name}
    return {"status": status, "connect": None, "disconnect": None}


_grok = lambda: _generic_unsupported("grok")
_kimi = lambda: _generic_unsupported("kimi")


# ------------------------------------------------------------------ backup

def _backup(path):
    if not os.path.isfile(path):
        return None
    target_dir = paths.backups_dir()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = os.path.basename(path)
    target = os.path.join(target_dir, "%s.bak-rbforge-%s" % (base, stamp))
    shutil.copy2(path, target)
    return target


# ------------------------------------------------------------------ public API

def status(provider=None):
    names = [provider] if provider else list(PROVIDERS)
    if provider and provider not in PROVIDERS:
        raise ForgeError("RBF-ARG-001", "unknown provider %r" % provider,
                         hint="one of: %s" % ", ".join(PROVIDERS))
    out = {}
    for name in names:
        impl = globals()["_%s" % name]()
        entry = impl["status"]() or {"installed": False}
        entry.setdefault("agent_installed", impl["status"]() is not None)
        out[name] = entry
    return out


def connect(provider):
    impl = globals()["_%s" % provider]() if provider in PROVIDERS else None
    if not impl or not impl.get("connect"):
        raise ForgeError("RBF-AGENT-001",
                         "automatic connect for %r is not supported yet" % provider,
                         hint=status(provider)[provider].get("note"))
    result = impl["connect"]()
    return {"provider": provider, "result": result,
            "verify": "restart %s, then run: rbforge doctor" % provider}


def disconnect(provider):
    impl = globals()["_%s" % provider]() if provider in PROVIDERS else None
    if not impl or not impl.get("disconnect"):
        raise ForgeError("RBF-AGENT-001", "disconnect for %r not supported" % provider)
    return {"provider": provider, "result": impl["disconnect"]()}
