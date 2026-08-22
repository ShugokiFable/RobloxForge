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

from . import paths
from .errors import ForgeError

PROVIDERS = ("hermes", "claude", "codex", "grok", "kimi")


def _mentions(text):
    """True when output names OUR server. Deliberately does NOT match
    'roblox-studio'/'roblox_studio' - that is the official Studio MCP, a
    different registration, and conflating the two would report the forge
    as configured on machines that only ever added the official one."""
    if not text:
        return False
    return "robloxforge" in text.lower()


# ------------------------------------------------------------------ helpers

def _run(cmd, timeout=120, feed=None):
    """feed: stdin text for CLIs that prompt (e.g. hermes mcp add's Y/n)."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              input=feed, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": str(exc)})()


# The forge's own MCP registration. Every provider wires it DISABLED so the
# 11 rb_* tool schemas do not ride along in unrelated sessions; users flip
# it on for Roblox work (see README "Token discipline").
FORGE_SERVER = "robloxforge"


def _forge_argv():
    """[python, <repo>/mcp_server/server.py] resolved from THIS checkout,
    so a clone anywhere works. Forward slashes: valid in Windows argv AND
    valid inside TOML basic strings (backslashes would need escaping and
    `\\U` in `C:\\Users` is a unicode escape that bricks codex's config)."""
    from . import paths
    script = os.path.join(paths.REPO_ROOT, "mcp_server", "server.py")
    return [sys.executable or "python", script.replace("\\", "/")]


def _toml_block(name, argv):
    """A TOML table for one stdio MCP server. argv MUST be forward-slashed."""
    safe = [a.replace("\\", "/") for a in argv]
    return ('\n[mcp_servers.%s]\ncommand = "%s"\nargs = ["%s"]\n'
            "enabled = false\n" % (name, safe[0], safe[1]))


def _toml_remove(text, name):
    """Delete ONLY the named server's keys from a TOML doc.

    Line-based, because blocks contain `args = [...]` whose `[` defeats any
    'up to next bracket' regex - and that regex variant also ate unrelated
    tables (it deleted the official Roblox_Studio entry). Never touches
    anything outside the named table.
    """
    out, skipping = [], False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("["):
            skipping = stripped == "[mcp_servers.%s]" % name
        if not skipping:
            out.append(line)
    return "".join(out)


def _toml_enabled(text, name):
    """enabled state of a parsed TOML table; None when absent/unparseable."""
    try:
        import tomllib
        data = tomllib.loads(text)
    except Exception:  # ValueError on py3.11-, tomllib.TOMLDecodeError subclass
        return None
    table = data.get("mcp_servers", {}).get(name)
    if not isinstance(table, dict):
        return None
    return bool(table.get("enabled", True))


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
                     "--args", *argv[1:]], timeout=180, feed="y\n")
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
            _backup(cfg_file)
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
        block = _toml_block(FORGE_SERVER, _forge_argv())
        _backup(cfg)
        with open(cfg, "a", encoding="utf-8") as handle:
            handle.write(block)
        if _toml_enabled(open(cfg, encoding="utf-8").read(), FORGE_SERVER) is None:
            raise ForgeError("RBF-AGENT-004",
                             "wrote %s but the file no longer parses as TOML" % cfg,
                             hint="restore from the .bak next to it and report this")
        return ("appended [mcp_servers.%s] (enabled=false) to %s (backup saved); "
                "flip enabled=true for Roblox sessions" % (FORGE_SERVER, cfg))

    def disconnect(cfg=None):
        cfg = cfg or cfg_path
        if not os.path.isfile(cfg):
            return "nothing to remove"
        _backup(cfg)
        text = open(cfg, encoding="utf-8", errors="replace").read()
        out = _toml_remove(text, FORGE_SERVER)
        open(cfg, "w", encoding="utf-8").write(out)
        return "removed robloxforge block from %s (official entries untouched; backup saved)" % cfg

    return {"status": status, "connect": connect, "disconnect": disconnect}


def _generic_unsupported(name):
    def status(_cfg=None):
        return {"configured": False, "note":
                "%s support not implemented; add the official MCP yourself:\n"
                '  command: cmd.exe  args: ["/c", "%%LOCALAPPDATA%%\\Roblox\\mcp.bat"]' % name}
    return {"status": status, "connect": None, "disconnect": None}


def _grok():
    cfg_path = os.path.join(os.path.expanduser("~"), ".grok", "config.toml")

    def status(cfg=None):
        cfg = cfg or cfg_path
        if not os.path.isfile(cfg):
            return None
        text = open(cfg, encoding="utf-8", errors="replace").read()
        present = _toml_enabled(text, FORGE_SERVER) is not None
        return {"configured": present,
                "enabled": _toml_enabled(text, FORGE_SERVER),
                "detail": "off by default; grok mcp enable robloxforge to use"}

    def connect(cfg=None):
        cfg = cfg or cfg_path
        st = status(cfg)
        if st and st["configured"]:
            return "already configured"
        _backup(cfg)
        with open(cfg, "a", encoding="utf-8") as fh:
            fh.write(_toml_block(FORGE_SERVER, _forge_argv()))
        return "added [mcp_servers.%s] (enabled=false) to %s" % (FORGE_SERVER, cfg)

    def disconnect(cfg=None):
        cfg = cfg or cfg_path
        if not os.path.isfile(cfg):
            return "nothing to remove"
        _backup(cfg)
        text = open(cfg, encoding="utf-8", errors="replace").read()
        out = _toml_remove(text, FORGE_SERVER)
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
        st = impl["status"]()
        entry = st or {"installed": False}
        entry.setdefault("agent_installed", st is not None)
        out[name] = entry
    return out


def connect(provider):
    results = {}
    for name in _as_names(provider):
        impl = globals()["_%s" % name]()
        if not impl.get("connect"):
            results[name] = {"provider": name,
                             "error": "automatic connect for %r is not supported yet" % name,
                             "hint": "add the official MCP manually; see README"}
            continue
        try:
            results[name] = {"provider": name, "result": impl["connect"](),
                             "verify": "restart %s, then run: rbforge doctor" % name}
        except ForgeError as exc:
            results[name] = exc.to_dict()
    return results[provider] if isinstance(provider, str) else results


def disconnect(provider):
    results = {}
    for name in _as_names(provider):
        impl = globals()["_%s" % name]()
        if not impl.get("disconnect"):
            results[name] = {"provider": name,
                             "error": "disconnect for %r not supported" % name}
            continue
        try:
            results[name] = {"provider": name, "result": impl["disconnect"]()}
        except ForgeError as exc:
            results[name] = exc.to_dict()
    return results[provider] if isinstance(provider, str) else results
