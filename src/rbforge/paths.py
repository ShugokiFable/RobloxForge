"""Path discovery. Nothing here may hardcode a drive letter or username."""
import os
import sys

from .errors import ForgeError

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _env_dir(name):
    v = os.environ.get(name)
    return v if v and os.path.isdir(v) else None


def local_appdata():
    """%LOCALAPPDATA% on Windows, XDG-ish equivalent elsewhere."""
    d = _env_dir("LOCALAPPDATA")
    if d:
        return d
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support")
    return os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")


def home():
    """RobloxForge's own writable state directory.

    Override with RBFORGE_HOME. Never inside the repo checkout by default so
    `git pull` and uninstall never destroy a user's docs cache.
    """
    env = os.environ.get("RBFORGE_HOME")
    if env:
        return _ensure(env)
    base = local_appdata()
    if base:
        return _ensure(os.path.join(base, "RobloxForge"))
    return _ensure(os.path.join(REPO_ROOT, ".rbforge-home"))


def _ensure(d):
    try:
        os.makedirs(d, exist_ok=True)
    except OSError as exc:
        raise ForgeError("RBF-ARG-002", "cannot create RobloxForge home %r: %s" % (d, exc),
                         hint="set RBFORGE_HOME to a writable directory")
    return d


def docs_cache_dir():
    return os.path.join(home(), "creator-docs")


def docs_state_file():
    return os.path.join(home(), "docs-cache.json")


def receipts_dir():
    return _ensure(os.path.join(home(), "receipts"))


def backups_dir():
    return _ensure(os.path.join(home(), "config-backups"))


def skills_source_dir():
    return os.path.join(REPO_ROOT, "skills")


def templates_dir():
    return os.path.join(REPO_ROOT, "templates")


def expand(p):
    """Expand %VARS%, $VARS and ~ the way a Windows user would expect."""
    if not p:
        return p
    return os.path.expanduser(os.path.expandvars(p))


def which(exe):
    """shutil.which, but also honours PATHEXT quirks and returns None quietly."""
    import shutil
    return shutil.which(exe)
