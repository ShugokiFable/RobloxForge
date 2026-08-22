"""Project detection & analysis.

Detects Studio-native vs Rojo projects on the filesystem. Live Studio-only
places are NOT analyzable from disk - the module says so and defers to the
official MCP instead of pretending.
"""
import json
import os
import re

from .errors import ForgeError

_LUAU_EXTS = (".lua", ".luau")


def detect(path):
    """Classify a directory. Returns dict; raises RBF-PROJECT-001 if absent."""
    if not os.path.isdir(path):
        raise ForgeError("RBF-PROJECT-001", "not a directory: %r" % path)
    rojo = None
    for name in ("default.project.json",):
        candidate = os.path.join(path, name)
        if os.path.isfile(candidate):
            rojo = candidate
    if not rojo:
        for name in os.listdir(path):
            if name.endswith(".project.json"):
                rojo = os.path.join(path, name)
                break
    style = "rojo" if rojo else "studio-native"
    return {"path": os.path.abspath(path), "style": style,
            "rojo_project": rojo,
            "note": ("live Studio places are not on disk; analyze via the "
                     "official MCP tools instead" if False else None)}


def _walk_sources(path):
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "node_modules", "__pycache__",
                                    ".sourcemap", "sourcemap")]
        for name in filenames:
            if name.lower().endswith(_LUAU_EXTS) or name.endswith((".server.lua",
                                                                   ".client.lua")):
                yield os.path.join(dirpath, name)


def analyze(path=None):
    path = path or os.getcwd()
    det = detect(path)

    scripts = {"server": [], "client": [], "module": [], "unknown": []}
    remotes = set()
    datastore_hits = []
    monoliths = []
    hazards = []

    _srv = re.compile(r"\.(server\.lua|server\.luau)$|(^|[\\/])Server[\\/]", re.I)
    _cli = re.compile(r"\.(client\.lua|client\.luau)$|(^|[\\/])Client[\\/]", re.I)

    total = 0
    for full in _walk_sources(det["path"]):
        total += 1
        rel = os.path.relpath(full, det["path"]).replace("\\", "/")
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError:
            continue
        low = text.lower()

        if ".server." in full or _srv.search(rel):
            kind = "server"
        elif ".client." in full or _cli.search(rel):
            kind = "client"
        else:
            kind = "module"

        scripts[kind].append({"path": rel, "lines": text.count("\n") + 1})

        for m in re.finditer(r"(RemoteEvent|RemoteFunction)\b", text):
            pass  # names alone are weak signal; instance creation is stronger
        for m in re.finditer(r'Instance\.new\("(RemoteEvent|RemoteFunction)"\)', text):
            remotes.add(m.group(1))
        if "getservice(\"datastoreservice\")" in low or "GetDataStore" in text:
            datastore_hits.append(rel)
        if "httprequest" in low and "post" in low:
            hazards.append({"file": rel, "why": "HttpService POST - verify destination"})
        if text.count("\n") + 1 > 400:
            monoliths.append({"file": rel, "lines": text.count("\n") + 1})

    # client-side authority smells
    for entry in scripts["client"]:
        full = os.path.join(det["path"], entry["path"])
        try:
            low = open(full, encoding="utf-8", errors="replace").read().lower()
        except OSError:
            continue
        for smell in ("leaderstats", "coins =", "coins+=", "damage", "humanoid.health ="):
            if smell in low:
                hazards.append({"file": entry["path"],
                                "why": "possible client-authority write: %r" % smell})
                break

    out = {
        **det,
        "script_count": total,
        "by_kind": {k: len(v) for k, v in scripts.items()},
        "scripts_over_400_lines": sorted(monoliths, key=lambda m: -m["lines"])[:10],
        "remote_types_created": sorted(remotes),
        "datastore_usage": datastore_hits[:20],
        "hazards": hazards[:30],
        "testing_setup": ("TestService present" if os.path.isdir(
            os.path.join(det["path"], "tests")) or _has_tests(det) else "none detected"),
        "limits": ["filesystem analysis only - live-only places need the official MCP",
                   "heuristic, not a proof: hazards are leads to read, not verdicts"],
    }
    return out


def _has_tests(det):
    for dirpath, dirnames, filenames in os.walk(det["path"]):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            if "test" in name.lower() and (name.endswith(".lua") or
                                           name.endswith(".spec.lua") or
                                           name.endswith("_spec.lua")):
                return True
        if dirpath.count(os.sep) > det["path"].count(os.sep) + 3:
            break
    return False
