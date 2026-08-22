"""Install/update/remove RobloxForge's two skills into supported agents.

Only ever touches directories WE own (`roblox-game-development`,
`roblox-docs`). A foreign skill with the same name is never overwritten -
that is reported as a manual decision instead. Versioned via a stamp file,
so `skills status` can say when an install is stale.
"""
import os
import shutil

from . import paths
from .errors import ForgeError

OUR_SKILLS = ("roblox-game-development", "roblox-docs")
STAMP = ".rbforge-version"

# Discovered skill roots on this machine class. Env override wins.
_ROOTS = {
    "hermes": ("RBFORGE_HERMES_SKILLS",
               ("%LOCALAPPDATA%\\hermes\\skills", "~/AppData/Local/hermes/skills")),
    "claude": ("RBFORGE_CLAUDE_SKILLS", ("~/.claude/skills",)),
    "codex": ("RBFORGE_CODEX_SKILLS", ("~/.codex/skills",)),
    "grok": ("RBFORGE_GROK_SKILLS", ("~/.grok/skills",)),
    "kimi": ("RBFORGE_KIMI_SKILLS", ("~/.kimi/skills",)),
}


def _expand(p):
    return paths.expand(p.replace("%LOCALAPPDATA%", "%LOCALAPPDATA%"))


def root_for(agent):
    """Where this agent keeps skills, if discoverable."""
    env_name, candidates = _ROOTS[agent]
    env = os.environ.get(env_name)
    if env and os.path.isdir(env):
        return env
    for cand in candidates:
        real = _expand(cand)
        if real and os.path.isdir(real):
            return real
    return None


def _installed_version(skill_dir):
    try:
        with open(os.path.join(skill_dir, STAMP), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def status():
    from . import __version__
    out = {}
    for agent in _ROOTS:
        root = root_for(agent)
        entry = {"root": root}
        if not root:
            entry["note"] = "skill directory not found"
            out[agent] = entry
            continue
        states = {}
        for name in OUR_SKILLS:
            d = os.path.join(root, name)
            if not os.path.isdir(d):
                states[name] = "absent"
                continue
            v = _installed_version(d)
            if v is None:
                states[name] = "foreign"  # exists but not ours - never clobber
            elif v != __version__:
                states[name] = "stale (%s -> %s)" % (v, __version__)
            else:
                states[name] = "current"
        entry["skills"] = states
        out[agent] = entry
    return out


def install(agents=None):
    """Copy our skills into each agent's root. Repeatable, reversible."""
    from . import __version__
    src_root = paths.skills_source_dir()
    targets = agents or list(_ROOTS)
    results = {}
    for agent in targets:
        if agent not in _ROOTS:
            raise ForgeError("RBF-ARG-001", "unknown agent %r" % agent,
                             hint="one of: %s" % ", ".join(_ROOTS))
        root = root_for(agent)
        if not root:
            results[agent] = "skipped: no skill directory found"
            continue
        copied = []
        for name in OUR_SKILLS:
            src = os.path.join(src_root, name)
            dst = os.path.join(root, name)
            if os.path.isdir(dst) and _installed_version(dst) is None:
                results[agent] = "blocked: %s exists and is not RobloxForge's" % name
                break
            if os.path.isdir(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            with open(os.path.join(dst, STAMP), "w", encoding="utf-8") as fh:
                fh.write(__version__)
            copied.append(name)
        else:
            results[agent] = "installed %s" % ", ".join(copied) if copied else "nothing to do"
    return results


def remove(agents=None):
    """Uninstall ONLY our skill dirs. Foreign content untouched."""
    targets = agents or list(_ROOTS)
    results = {}
    for agent in targets:
        root = root_for(agent)
        if not root:
            results[agent] = "no skill directory"
            continue
        removed = []
        for name in OUR_SKILLS:
            d = os.path.join(root, name)
            if os.path.isdir(d) and _installed_version(d) is not None:
                shutil.rmtree(d)
                removed.append(name)
        results[agent] = "removed %s" % ", ".join(removed) if removed else "nothing of ours present"
    return results
