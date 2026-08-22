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
import sys
import time

from . import paths, studio
from .errors import ForgeError

PROVIDERS = ("hermes", "claude", "codex", "grok", "kimi")


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


# The forge's own MCP registration. Every provider wires it DISABLED so the
# 11 rb_* tool schemas do not ride along in unrelated sessions; users flip
# it on for Roblox work (see README "Token discipline").
FORGE_SERVER = "robloxforge"


def _forge_argv():
    """[python, <repo>/mcp_server/server.py] resolved from THIS checkout,
    so a clone anywhere works."""
    from . import paths
    script = os.path.join(paths.REPO_ROOT, "mcp_server", "server.py")
    return [sys.executable or "python", script]


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
        argv = _forge_argv()
        # `hermes mcp add` prompts "Enable all tools? [Y/n]" interactively;
        # pipe 'y' or it cancels silently.
        done = _run([exe, "mcp", "add", FORGE_SERVER, "--command", argv[0],
                     "--args", *argv[1:]], timeout=180)
        if "Saved" not in (done.stdout or ""):
            raise ForgeError(
                "RBF-AGENT-002", "hermes mcp add did not save the server",
                hint="run manually: hermes mcp add %s --command %s --args \"%s\" "
                     "(answer Y at the tool-enable prompt), then: "
                     "hermes config set mcp_servers.%s.enabled false "
                     "(off by default; enable for Roblox sessions)"
                     % (FORGE_SERVER, argv[0], argv[1], FORGE_SERVER))
        _run([exe, "config", "set", "mcp_servers.%s.enabled" % FORGE_SERVER,
              "false"])
        return "added via `hermes mcp add`, disabled by default"

    def disconnect(_cfg=None):
        _run([exe, "mcp", "remove", FORGE_SERVER])
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
        argv = _forge_argv()
        # user scope so it is not tied to one project directory
        if not _run([exe, "mcp", "add", "--scope", "user", FORGE_SERVER,
                     "--", *argv]).returncode == 0:
            raise ForgeError("RBF-AGENT-003", "claude mcp add failed",
                             hint="run manually: claude mcp add --scope user %s -- %s"
                                  % (FORGE_SERVER, " ".join(argv)))
        # Claude has no global off-switch: seed every known project entry
        # (and future sessions inherit from these) with the disable array.
        # New directories start enabled - documented in README.
        cfg_file = os.path.join(os.path.expanduser("~"), ".claude.json")
        try:
            data = json.load(open(cfg_file, encoding="utf-8"))
            n = 0
            for proj in (data.get("projects") or {}).values():
                arr = proj.setdefault("disabledMcpServers", [])
                if FORGE_SERVER not in arr:
                    arr.append(FORGE_SERVER)
                    n += 1
            json.dump(data, open(cfg_file, "w", encoding="utf-8"), indent=2)
            return ("added via `claude mcp add --scope user`; disabled in %d "
                    "known project(s) - toggle on per-session with /mcp" % n)
        except (OSError, ValueError):
            return "added via `claude mcp add --scope user` (could not auto-disable)"

    def disconnect(_cfg=None):
        _run([exe, "mcp", "remove", "-s", "user", FORGE_SERVER])
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
        argv = _forge_argv()
        block = ('\n[mcp_servers.%s]\ncommand = "%s"\nargs = ["%s"]\n'
                 "enabled = false\n" % (FORGE_SERVER, argv[0], argv[1]))
        _backup(cfg)
        with open(cfg, "a", encoding="utf-8") as handle:
            handle.write(block)
        return ("appended [mcp_servers.%s] (enabled=false) to %s (backup saved); "
                "flip enabled=true for Roblox sessions" % (FORGE_SERVER, cfg))

    def disconnect(cfg=None):
        cfg = cfg or cfg_path
        if not os.path.isfile(cfg):
            return "nothing to remove"
        _backup(cfg)
        text = open(cfg, encoding="utf-8", errors="replace").read()
        out = re.sub(r"\n?\[mcp_servers\.(?:%s|Roblox_Studio)\]\n(?:[^\[]*\n)?"
                     % FORGE_SERVER, "\n", text)
        open(cfg, "w", encoding="utf-8").write(out)
        return "removed robloxforge block from %s (backup saved)" % cfg

    return {"status": status, "connect": connect, "disconnect": disconnect}


def _generic_unsupported(name):
    def status(_cfg=None):
        return {"configured": False, "note":
                "%s support not implemented; add the official MCP yourself:\n"
                '  command: cmd.exe  args: ["/c", "%%LOCALAPPDATA%%\\Roblox\\mcp.bat"]' % name}
    return {"status": status, "connect": None, "disconnect": None}


def _grok():
    cfg_path = os.path.join(os.path.expanduser("~"), ".grok", "config.toml")
    block = ('\n[mcp_servers.robloxforge]\ncommand = "python"\n'
             'args = ["S:/Apps/Roblox Tools/RobloxForge/mcp_server/server.py"]\n'
             "enabled = false\n")

    def status(cfg=None):
        cfg = cfg or cfg_path
        if not os.path.isfile(cfg):
            return None
        text = open(cfg, encoding="utf-8", errors="replace").read()
        present = "[mcp_servers.robloxforge]" in text
        off = bool(re.search(r"\[mcp_servers\.robloxforge\][^\[]*?enabled\s*=\s*false",
                             text, re.S))
        return {"configured": present, "enabled": not off,
                "detail": "off by default; grok mcp enable robloxforge to use"}

    def connect(cfg=None):
        cfg = cfg or cfg_path
        st = status(cfg)
        if st and st["configured"]:
            return "already configured"
        _backup(cfg)
        with open(cfg, "a", encoding="utf-8") as fh:
            fh.write(block)
        return "added [mcp_servers.robloxforge] (enabled=false) to %s" % cfg

    def disconnect(cfg=None):
        cfg = cfg or cfg_path
        if not os.path.isfile(cfg):
            return "nothing to remove"
        _backup(cfg)
        text = open(cfg, encoding="utf-8", errors="replace").read()
        out = re.sub(r"\n?\[mcp_servers\.robloxforge\]\n(?:[^\[]*\n)?", "\n", text)
        open(cfg, "w", encoding="utf-8").write(out)
        return "removed robloxforge block from %s (backup saved)" % cfg

    return {"status": status, "connect": connect, "disconnect": disconnect}


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
