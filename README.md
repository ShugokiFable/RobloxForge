# RobloxForge

RobloxForge is a free, local-first AI development workbench that teaches
general AI agents how to build, test, debug and verify Roblox games using
Roblox Studio's official MCP and current Roblox documentation.

**The problem it solves:** a good general model + the official Roblox Studio
MCP technically gives an agent Studio control, but it still builds bad games —
wrong architecture, no playtesting, stale API knowledge, "done" declared on
untested code. RobloxForge is the missing intelligence layer: current docs,
vertical-slice discipline, ownership rules, security rules, verification
receipts.

**What it is NOT:** another Studio MCP. The official one (built into Roblox
Studio) owns the live engine. RobloxForge never duplicates it.

## Quickstart

```
START-HERE.bat          # or: python src\rbforge_cli.py doctor
```

```
rbforge doctor                      # full health report, each fact independent
rbforge docs update                 # fetch official creator-docs (27 MB, git-sparse)
rbforge docs search "ProcessReceipt"
rbforge agent connect hermes        # wire the official Roblox MCP into an agent
rbforge skills install all          # install the two RobloxForge skills
rbforge capabilities                # honest capability matrix (probed, not assumed)
```

## Connecting agents (installed OFF by default — token discipline)

The 11 `rb_*` MCP tools are useful during Roblox work but waste context in
every other session. `rbforge agent connect` therefore wires the forge's
MCP server **disabled** into each agent, and installs the two skills
(always-on; they cost nothing until a Roblox prompt triggers them):

```
rbforge agent connect all       # or: hermes | claude | codex | grok
rbforge skills install all
rbforge agent status
```

Per-agent enable/disable:

| Agent | Wired as | Enable for a Roblox session |
|---|---|---|
| Hermes | `robloxforge`, `enabled: false` | `hermes config set mcp_servers.robloxforge.enabled true`, restart |
| Claude Code | user-scope + per-project disable array | `/mcp` toggle in-session (no global off-switch exists; brand-new dirs start enabled) |
| Codex | `[mcp_servers.robloxforge] enabled = false` | flip the flag in `~/.codex/config.toml` |
| Grok | same TOML shape | `grok mcp enable robloxforge` |

Disable again when done to reclaim the tool schemas. The official Roblox
Studio MCP (`roblox-studio` / `mcp.bat`) is separate and stays enabled — it
is only useful when Studio is open anyway.

## The two skills (the actual product)

- **roblox-game-development** — router skill: vertical slices per genre,
  server/client ownership, security rules, playtest contract, sharp edges.
- **roblox-docs** — current-knowledge system: search + read the official
  `Roblox/creator-docs` corpus locally, freshness reported honestly.

Resolution priority baked into both: observed runtime > current official
docs > verified community practice > model memory.

## Components

| Piece | What |
|---|---|
| `src/rbforge_cli.py` | CLI — every command prints JSON |
| `mcp_server/server.py` | 11-tool MCP server (doctor, capabilities, docs, planning, reviews, receipts) |
| `skills/` | the two agent skills, installed into Hermes/Claude/Codex/Grok/Kimi |
| `tests/run_tests.py` | 20 checks, no Roblox required |

Register the MCP server manually (all agents, disabled) instead:

```
python src\rbforge_cli.py agent connect all
```

## Status (v0.1.1 — honest)

| Area | Status |
|---|---|
| Studio + official MCP detection & live handshake probe | verified on Windows 11 |
| creator-docs sparse cache (2,199 docs) + ranked search | verified |
| Doctor, capabilities matrix | verified |
| Skill install into Hermes (live), Claude/Codex/Grok/Kimi roots | verified |
| Vertical-slice planning, reviews, verification receipts | implemented, static-only |
| Real E2E weak-model benchmark (baseline vs RobloxForge obby) | **not yet run** |

v1.0.0 waits for the E2E benchmark proving behavioral improvement. See
`docs/BENCHMARK.md`.

## Trademark notice

Not affiliated with, endorsed by, or sponsored by Roblox Corporation.
"Roblox" and "Roblox Studio" are trademarks of Roblox Corporation, used
here descriptively. Roblox documentation is fetched at runtime from
Roblox's public repository (CC-BY-4.0) and never redistributed by this repo.
