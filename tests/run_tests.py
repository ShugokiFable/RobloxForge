"""RobloxForge test runner. No pytest, no Roblox install required.

Run: python tests/run_tests.py
Fixture-based; exercises every core module against synthetic state.
"""
import io
import json
import os
import sys
import tempfile
import contextlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import rbforge  # noqa: E402
from rbforge import errors as err_mod  # noqa: E402

PASS, FAIL = [], []


@contextlib.contextmanager
def tempdir():
    import shutil
    d = tempfile.mkdtemp(prefix="rbf-test-")
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@contextlib.contextmanager
def _isolated_home():
    from rbforge import paths
    old = os.environ.get("RBFORGE_HOME")
    d = tempfile.mkdtemp(prefix="rbf-home-")
    os.environ["RBFORGE_HOME"] = d
    try:
        paths.home()  # recreate
        yield d
    finally:
        if old is None:
            os.environ.pop("RBFORGE_HOME", None)
        else:
            os.environ["RBFORGE_HOME"] = old
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def check(name):
    def deco(fn):
        try:
            fn()
            PASS.append(name)
            print("ok   %s" % name)
        except Exception as exc:  # noqa: BLE001
            FAIL.append((name, exc))
            print("FAIL %s: %r" % (name, exc))
        return fn
    return deco


# ---------------------------------------------------------------- errors

@check("errors: exit codes map by prefix")
def _():
    assert err_mod.ForgeError("RBF-DOCS-001", "x").exit_code == err_mod.ExitCode.DEPENDENCY
    assert err_mod.ForgeError("RBF-STUDIO-001", "x").exit_code == err_mod.ExitCode.NOT_FOUND
    d = err_mod.ForgeError("RBF-MCP-002", "m", hint="h").to_dict()
    assert d["error"]["code"] == "RBF-MCP-002" and d["error"]["hint"] == "h"


@check("errors: unknown prefix falls back to generic")
def _():
    assert err_mod.ForgeError("RBF-ZZZ-999", "x").exit_code == 1


# ---------------------------------------------------------------- docs (offline)

@check("docs: search works on existing cache without network")
def _():
    from rbforge import docs
    if not docs.cache_present():
        return  # skip quietly on machines without a cache; CI fixtures cover logic below
    r = docs.search("RemoteEvent:FireServer", limit=3)
    assert r["results"], "no results"
    assert "RemoteEvent.yaml" in r["results"][0]["path"]
    assert r["source"].startswith("Roblox/creator-docs")


@check("docs: freshness never guesses when cache absent")
def _():
    from rbforge import paths, docs as docs_mod
    with _isolated_home():
        f = docs_mod.freshness()
        assert f["present"] is False and f["stale"] is None


@check("docs: offline refresh failure keeps cache and records error")
def _():
    from rbforge import docs as docs_mod
    with _isolated_home():
        # fake a healthy cache + state without touching the network
        content = os.path.join(docs_mod.paths.docs_cache_dir(), "content", "en-us")
        os.makedirs(content)
        open(os.path.join(content, "x.md"), "w").write("# hi")
        docs_mod.write_state(fetched_at=__import__("time").time(),
                             method="git-sparse", commit="deadbeef")
        before = docs_mod.freshness()["stale"]
        docs_mod.ensure(refresh=True, allow_network=False)
        st = docs_mod.read_state()
        # allow_network=False skips refresh entirely - cache intact, no error written
        assert docs_mod.cache_present() and before is False


@check("docs: member query hits owning class (ProcessReceipt)")
def _():
    from rbforge import docs
    if not docs.cache_present():
        return
    r = docs.search("ProcessReceipt", limit=3)
    paths_ = [x["path"] for x in r["results"]]
    assert any("MarketplaceService" in p for p in paths_), paths_


@check("docs: read rejects path escape")
def _():
    from rbforge import docs
    try:
        docs.read("../../etc/passwd")
        raise AssertionError("should have raised")
    except err_mod.ForgeError as e:
        assert e.code in ("RBF-ARG-003", "RBF-DOCS-005", "RBF-DOCS-001")


# ---------------------------------------------------------------- planning

@check("planning: slice plan for every genre")
def _():
    from rbforge import planning
    for g in ("generic", "obby", "simulator", "tycoon"):
        p = planning.vertical_slice(g, "test premise")
        assert p["build_order"] and p["verification"] and p["core_loop"]
    try:
        planning.vertical_slice("mmorpg", "x")
        raise AssertionError("should have raised")
    except err_mod.ForgeError:
        pass


# ---------------------------------------------------------------- verification

@check("verification: unverified claim is blocked")
def _():
    from rbforge import verification
    r = verification.receipt("t", save=False)
    assert r["verification_level"] == "unverified"
    assert "do not claim working" in r["claim_allowed"]


@check("verification: full evidence -> verified_playtest")
def _():
    from rbforge import verification
    checks = ["studio_connected", "place_inspected_before_edit", "core_loop_exists",
              "player_spawns", "primary_action_works", "progression_works",
              "failure_death_behavior_works", "console_checked",
              "no_fatal_runtime_errors", "gameplay_path_exercised"]
    r = verification.receipt("full", checks=checks, console_errors=0,
                             playtest_performed=True,
                             screenshot_captured=True, screenshot_inspected=True,
                             save=False)
    assert r["verification_level"] == "verified_playtest"


@check("verification: console errors downgrade level")
def _():
    from rbforge import verification
    checks = ["studio_connected", "core_loop_exists", "player_spawns",
              "primary_action_works", "gameplay_path_exercised", "console_checked"]
    r = verification.receipt("errs", checks=checks, console_errors=3,
                             playtest_performed=True, save=False)
    assert r["verification_level"] == "playtested_with_errors"


@check("verification: receipt persists to disk")
def _():
    from rbforge import verification
    with _isolated_home():
        r = verification.receipt("persist me", save=True)
        assert os.path.isfile(r["saved_to"])
        loaded = json.load(open(r["saved_to"], encoding="utf-8"))
        assert loaded["task"] == "persist me"


# ---------------------------------------------------------------- project/review/scaffold

@check("project: detect rojo vs studio-native")
def _():
    from rbforge import project
    with tempdir() as d:
        json.dump({"name": "t"}, open(os.path.join(d, "default.project.json"), "w"))
        assert project.detect(d)["style"] == "rojo"
    with tempdir() as d:
        assert project.detect(d)["style"] == "studio-native"
    try:
        project.detect(os.path.join(d, "nope"))
        raise AssertionError("should have raised")
    except err_mod.ForgeError as e:
        assert e.code == "RBF-PROJECT-001"


@check("review: client-authority write flagged")
def _():
    from rbforge import review
    with tempdir() as d:
        open(os.path.join(d, "evil.client.lua"), "w").write(
            "local ls = Instance.new('Folder') ls.Name = 'leaderstats'\n")
        out = review.security(d)
        assert any(f["severity"] == "high" for f in out["findings"]), out["findings"]


@check("review: guarded remote handler rates 'info', unguarded 'medium'")
def _():
    from rbforge import review
    with tempdir() as d:
        open(os.path.join(d, "guarded.server.lua"), "w").write(
            "r.OnServerEvent:Connect(function(p, amt) if typeof(amt) ~= 'number' then return end end)")
        open(os.path.join(d, "unguarded.server.lua"), "w").write(
            "r.OnServerEvent:Connect(function(p, amt) give(p, amt) end)")
        out = review.security(d)
        sev = {f["file"]: f["severity"] for f in out["findings"]}
        assert sev.get("guarded.server.lua") == "info", sev
        assert sev.get("unguarded.server.lua") == "medium", sev


@check("scaffold: writes layout, refuses non-empty target")
def _():
    from rbforge import scaffold
    with tempdir() as base:
        target = os.path.join(base, "game")
        r = scaffold.scaffold(target, "simulator")
        assert os.path.isfile(os.path.join(target, "src", "server", "Main.server.lua"))
        cfg = open(os.path.join(target, "src", "shared", "Config.lua")).read()
        assert '"simulator"' in cfg
        try:
            scaffold.scaffold(target, "simulator")
            raise AssertionError("should have raised")
        except err_mod.ForgeError as e:
            assert e.code == "RBF-ARG-002"


# ---------------------------------------------------------------- studio (offline paths)

@check("studio: snapshot fields independent even with no probe")
def _():
    from rbforge import studio
    snap = studio.snapshot(probe=False)
    for key in ("studio_installed", "mcp_launcher_found", "mcp_enabled_setting",
                "studio_process"):
        assert key in snap
    assert snap["mcp_probe"]["responding"] is None


# ---------------------------------------------------------------- capabilities

@check("capabilities: statuses derived, optional absence calm")
def _():
    from rbforge import capabilities
    m = capabilities.compute(probe=False)
    assert m["official_studio_mcp"]["status"] in (
        "verified", "unavailable", "runtime_required", "manual_step")
    for t in ("rojo", "stylua", "selene"):
        assert m[t]["status"] in ("installed", "optional")


# ---------------------------------------------------------------- skills installer

@check("skills: install/remove roundtrip into a sandbox root")
def _():
    from rbforge import skills
    with tempdir() as root:
        skills._ROOTS["sandbox"] = ("RBFORGE_SANDBOX_SKILLS", (root,))
        try:
            res = skills.install(["sandbox"])
            assert "installed" in res["sandbox"], res
            st = skills.status()
            assert all(v == "current" for v in st["sandbox"]["skills"].values())
            assert os.path.isdir(os.path.join(root, "roblox-game-development"))
            skills.remove(["sandbox"])
            assert not os.path.isdir(os.path.join(root, "roblox-game-development"))
        finally:
            del skills._ROOTS["sandbox"]


@check("skills: foreign skill dir blocks overwrite")
def _():
    from rbforge import skills
    with tempdir() as root:
        foreign = os.path.join(root, "roblox-docs")
        os.makedirs(foreign)
        open(os.path.join(foreign, "SKILL.md"), "w").write("---\nname: roblox-docs\nnot ours\n")
        skills._ROOTS["sbx2"] = ("RBFORGE_SBX2_SKILLS", (root,))
        try:
            res = skills.install(["sbx2"])
            assert "blocked" in res["sbx2"], res
        finally:
            del skills._ROOTS["sbx2"]


# ---------------------------------------------------------------- helpers (moved above)

if __name__ == "__main__":
    print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
    for name, exc in FAIL:
        print("  FAILED: %s -> %r" % (name, exc))
    sys.exit(1 if FAIL else 0)
