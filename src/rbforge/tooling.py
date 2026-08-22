"""Optional Luau toolchain detection. Detection only - never auto-installs.

All of these are optional. Absence is reported as `optional`, not failure;
they only matter for the source-controlled (Rojo) workflow.
"""
import re
import shutil
import subprocess

TOOLS = {
    "rojo":     {"purpose": "sync filesystem project into Studio"},
    "stylua":   {"purpose": "Luau formatter"},
    "selene":   {"purpose": "Luau linter"},
    "luau-lsp": {"purpose": "type checking / autocomplete data"},
    "rokit":    {"purpose": "installs the others, pinned per-project"},
}

_VERSION = re.compile(r"([0-9]+\.[0-9]+[0-9a-zA-Z.\-]*)")


def _probe_version(path):
    """First version-looking token from `<exe> --version`. Never raises."""
    try:
        done = subprocess.run([path, "--version"], capture_output=True,
                              text=True, timeout=15)
        text = (done.stdout or "") + (done.stderr or "")
        match = _VERSION.search(text)
        return match.group(1) if match else None
    except (OSError, subprocess.SubprocessError):
        return None


def status():
    out = {}
    for name, meta in TOOLS.items():
        path = shutil.which(name)
        entry = {"found": bool(path), "purpose": meta["purpose"]}
        if path:
            entry["path"] = path
            entry["version"] = _probe_version(path)
        out[name] = entry
    return out


def recommend(project_style="studio-native"):
    """What to install for a given workflow. Honest: studio-native needs none."""
    if project_style == "studio-native":
        return []
    have = status()
    wanted = ["rokit", "rojo", "stylua", "selene"]
    return [{"tool": t, "purpose": TOOLS[t]["purpose"],
             "already_installed": bool(have[t]["found"])}
            for t in wanted if not have[t]["found"]]
