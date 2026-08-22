#!/usr/bin/env python3
"""rbforge CLI - every MCP tool has a CLI equivalent here.

Exit codes: 0 ok, 1 generic, 2 validation, 3 not-found, 4 dependency, 5 refused.
All output is JSON (machine-readable by default).
"""
import argparse
import json
import sys

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rbforge.errors import ForgeError, ExitCode


def _emit(obj):
    print(json.dumps(obj, indent=2, default=str))


def _fail(exc):
    _emit(exc.to_dict())
    return exc.exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(prog="rbforge",
                                     description="RobloxForge - AI-operable Roblox development workbench")
    sub = parser.add_subparsers(dest="cmd")

    p_doc = sub.add_parser("doctor", help="full health report")
    p_doc.add_argument("--no-probe", action="store_true", help="skip live MCP handshake")
    p_doc.add_argument("--vision", choices=["yes", "no"], default=None,
                       help="declare whether the host model can inspect images")

    sub.add_parser("capabilities", help="honest capability matrix")

    p_docs = sub.add_parser("docs", help="creator-docs knowledge cache")
    p_docs.add_argument("action", choices=["status", "update", "search", "read"])
    p_docs.add_argument("query", nargs="?", help="search query or document path")
    p_docs.add_argument("--limit", type=int, default=8)
    p_docs.add_argument("--around", help="read around this phrase")

    p_tools = sub.add_parser("tools", help="optional Luau toolchain status")
    p_tools.add_argument("action", nargs="?", default="status", choices=["status"])

    p_agents = sub.add_parser("agent", help="agent MCP wiring + skills")
    p_agents.add_argument("action", choices=["status", "connect", "disconnect"])
    p_agents.add_argument("name", nargs="?", help="hermes|claude|codex (or 'all')")

    p_skills = sub.add_parser("skills", help="install/update RobloxForge skills into agents")
    p_skills.add_argument("action", choices=["status", "install", "update", "remove"])
    p_skills.add_argument("name", nargs="?", help="hermes|claude|codex|grok|kimi or all")

    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return ExitCode.OK

    try:
        return _dispatch(args)
    except ForgeError as exc:
        return _fail(exc)


def _dispatch(args):
    from rbforge import agents, capabilities, doctor, docs as docs_mod, skills, tooling

    if args.cmd == "doctor":
        report = doctor.collect(probe=not args.no_probe,
                                host_vision={"yes": True, "no": False}.get(args.vision))
        if args.no_probe:
            pass  # render handles missing probe gracefully
        print(doctor.render(report))
        return ExitCode.OK

    if args.cmd == "capabilities":
        _emit(capabilities.compute(host_vision=None))
        return ExitCode.OK

    if args.cmd == "docs":
        if args.action == "status":
            _emit(docs_mod.freshness())
        elif args.action == "update":
            _emit(docs_mod.ensure(refresh=True))
        elif args.action == "search":
            if not args.query:
                raise ForgeError("RBF-ARG-001", "docs search needs a query",
                                 hint='rbforge docs search "TweenService:Create"')
            _emit(docs_mod.search(args.query, limit=args.limit))
        elif args.action == "read":
            if not args.query:
                raise ForgeError("RBF-ARG-001", "docs read needs a path",
                                 hint="use a path returned by docs search")
            _emit(docs_mod.read(args.query, around=args.around))
        return ExitCode.OK

    if args.cmd == "tools":
        _emit(tooling.status())
        return ExitCode.OK

    if args.cmd == "agent":
        names = None if (not args.name or args.name == "all") else [args.name]
        if args.action == "status":
            st = agents.status(names)
            _emit(st)
        elif args.action == "connect":
            _emit(agents.connect(names))
        elif args.action == "disconnect":
            _emit(agents.disconnect(names))
        return ExitCode.OK

    if args.cmd == "skills":
        names = None if (not args.name or args.name == "all") else [args.name]
        if args.action == "status":
            # status() covers every agent at once; filter client-side
            st = skills.status()
            _emit(st if names is None else {k: v for k, v in st.items()
                                            if k in names})
        else:
            fn = {"install": skills.install, "update": skills.install,
                  "remove": skills.remove}[args.action]
            _emit(fn(names))
        return ExitCode.OK

    return ExitCode.GENERIC


if __name__ == "__main__":
    sys.exit(main())
