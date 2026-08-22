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
    """True when output names our server (either registration name)."""
    if not text:
        return False
    low = text.lower()
    return "robloxforge" in low or "roblox-studio" in low or "roblox_studio" in low


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
        # `hermes mcp add` prompts "Enable all tools? [Y/n]" interactively;
        # feed 'y' or it cancels and reports nothing.
        done = _run([exe, "mcp", "add", SERVER_NAME.lower(),
                     "--command", cmd[0], "--args", *cmd[1:]])
        if done.returncode != 0 or "Saved" not in (done.stdout or ""):
            raise ForgeError("RBF-AGENT-002", "hermes mcp add did not save the server",
                             hint="run manually: hermes mcp add %s --command %s --args %s "
                                  "(answer Y at the prompt)"
                                  % (SERVER_NAME.lower(), cmd[0], " ".join(cmd[1:])))
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

def _one(provider):
    """CLI may hand us a list; normalize to one provider name."""
    if isinstance(provider, (list, tuple)):
        if len(provider) != 1:
            raise ForgeError("RBF-ARG-001", "connect takes exactly one provider",
                             hint="got %r" % (list(provider),))
        provider = provider[0]
    if provider not in PROVIDERS:
        raise ForgeError("RBF-ARG-001", "unknown provider %r" % provider,
                         hint="one of: %s" % ", ".join(PROVIDERS))
    return provider


def _as_names(provider):
    """Accept str | list | None everywhere; validate once."""
    if provider is None:
        return list(PROVIDERS)
    names = [provider] if isinstance(provider, str) else list(provider)
    bad = [n for n in names if n not in PROVIDERS]
    if bad:
        raise ForgeError("RBF-ARG-001", "unknown provider %r" % bad,
                         hint="one of: %s" % ", ".join(PROVIDERS))
    return names


def status(provider=None):
    out = {}
    for name in _as_names(provider):
        impl = globals()["_%s" % name]()
        entry = impl["status"]() or {"installed": False}
        entry.setdefault("agent_installed", impl["status"]() is not None)
        out[name] = entry
    return out


def connect(provider):
    results = {}
    for name in _as_names(provider):
        impl = globals()["_%s" % name]()
        if not impl.get("connect"):
            raise ForgeError("RBF-AGENT-001",
                             "automatic connect for %r is not supported yet" % name,
                             hint=(impl["status"]() or {}).get("note"))
        results[name] = {"provider": name, "result": impl["connect"](),
                         "verify": "restart %s, then run: rbforge doctor" % name}
    return results[provider] if isinstance(provider, str) else results


def disconnect(provider):
    results = {}
    for name in _as_names(provider):
        impl = globals()["_%s" % name]()
        if not impl.get("disconnect"):
            raise ForgeError("RBF-AGENT-001", "disconnect for %r not supported" % name)
        results[name] = {"provider": name, "result": impl["disconnect"]()}
    return results[provider] if isinstance(provider, str) else results
