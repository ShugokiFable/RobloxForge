# External Source Manifest

Upstream sources RobloxForge depends on or studied. Nothing here is
vendored into the repository; docs are fetched to the user's machine at
runtime.

| Source | Upstream | Purpose | Update policy | License |
|---|---|---|---|---|
| Creator documentation | https://github.com/Roblox/creator-docs (branch main) | the searchable knowledge corpus (`rb_docs_search`) | sparse blobless git fetch; refreshed on `rbforge docs update`; stale after 24h (reported honestly, never silently used as current) | CC-BY-4.0 (prose), MIT-style LICENSE-CODE (samples) |
| Official Studio MCP docs | https://create.roblox.com/docs/studio/mcp (+ source in creator-docs `content/en-us/studio/mcp.md`) | setup instructions, tool surface reference | read from the docs cache; live tool surface always probed at runtime because it moves with Studio updates | CC-BY-4.0 |
| Luau language docs | https://luau.org | syntax/semantics reference for skill content | consulted manually during authoring; not cached | MIT (site content) |
| Roblox/luau | https://github.com/Roblox/luau | upstream language repo, referenced in tooling notes | n/a (reference only) | MIT |

## Community projects studied (not copied)

Studied for pattern comparison during design; clean-room synthesis used.

| Repo | License | Notes |
|---|---|---|
| brockmartin/roblox-game-skill | none declared | studied structure; no code/text reused — no license means no reuse |
| zilibobi/roblox-skills | none declared | same |
| gogolumo/rbsmithy-roblox-claude-skill | NOASSERTION | same |
| CodePhobiia/claude-roblox-game-studio | MIT | concepts noted; no verbatim reuse |

Several target the ARCHIVED standalone MCP server (`Roblox/studio-rust-mcp-server`,
archived 2026-04); their assumptions about the tool surface are outdated.
RobloxForge targets the built-in server and probes its live surface instead
of hardcoding one.
