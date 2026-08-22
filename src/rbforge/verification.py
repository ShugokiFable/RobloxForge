"""Verification receipts: evidence records, not claims.

A receipt says what was and was not proven. Claims without playtest
evidence are recorded as UNVERIFIED - the receipt is honest even when the
agent writing it is optimistic.
"""
import json
import os
import time

from . import paths


def _required_checks():
    return {
        "studio_connected": False,
        "place_inspected_before_edit": False,
        "core_loop_exists": False,
        "player_spawns": False,
        "primary_action_works": False,
        "progression_works": False,
        "failure_death_behavior_works": False,
        "console_checked": False,
        "no_fatal_runtime_errors": False,
        "gameplay_path_exercised": False,
        "screenshot_captured": False,
        "screenshot_inspected": False,
    }


def receipt(task, checks=None, console_errors=0, playtest_performed=False,
            screenshot_captured=False, screenshot_inspected=False,
            limitations=None, project=None, save=True):
    """Build (and by default persist) a verification receipt.

    `checks` may name any of the standard check ids as done. Everything else
    stays explicitly false - absence of evidence is recorded as such.
    """
    state = _required_checks()
    for name in (checks or []):
        if name in state:
            state[name] = True

    gameplay_evidence = all(state[k] for k in (
        "studio_connected", "core_loop_exists", "player_spawns",
        "primary_action_works", "gameplay_path_exercised", "console_checked"))
    visual_evidence = bool(screenshot_captured and screenshot_inspected)

    if gameplay_evidence and playtest_performed and console_errors == 0:
        level = "verified_playtest"
    elif gameplay_evidence and playtest_performed:
        level = "playtested_with_errors"
    elif gameplay_evidence:
        level = "static_only"
    else:
        level = "unverified"

    rec = {
        "task": task,
        "project": project,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "checks": state,
        "console_errors_reported": int(console_errors or 0),
        "playtest_performed": bool(playtest_performed),
        "screenshot_captured": bool(screenshot_captured),
        "screenshot_inspected_by_vision": bool(screenshot_inspected),
        "verification_level": level,
        "claim_allowed": {
            "verified_playtest": "working (as tested)",
            "playtested_with_errors": "works with known errors - FIX BEFORE CLAIMING DONE",
            "static_only": "exists; NOT runtime-proven",
            "unverified": "unverified - do not claim working",
        }[level],
        "limitations": limitations or [],
    }
    if save:
        out_dir = paths.receipts_dir()
        stamp = time.strftime("%Y%m%d-%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in task)[:60]
        file_path = os.path.join(out_dir, "%s-%s.json" % (stamp, safe or "receipt"))
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=2)
        rec["saved_to"] = file_path
    return rec
