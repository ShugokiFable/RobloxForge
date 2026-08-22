# RobloxForge Knowledge Booster v1

Drop-in overlay for an in-progress RobloxForge checkout.

## Install

Extract this ZIP **over the root that already contains `RobloxForge/`**.

It intentionally does **not** replace:
- the existing Python core,
- the existing `roblox-game-development/SKILL.md`,
- the existing `references/studio-mcp.md`,
- provider configs,
- the official Roblox Studio MCP.

It fills the missing knowledge/reference layer visible in the supplied RobloxForge snapshot and adds optional scaffolds/benchmarks.

## What this adds

- 7 missing references already named by `roblox-game-development/SKILL.md`
- Roblox built-in Assistant skills routing guide
- performance, tooling, and game-design references
- a real `roblox-docs/SKILL.md`
- current-upstream source/toolchain manifest
- a source-controlled Rojo/Rokit starter template
- weak-model benchmark prompts
- adversarial security/UI/debug test prompts

## Design rule

Roblox Studio MCP = hands.

RobloxForge = brain, workflow, current knowledge, verification.

Do not connect a second giant Studio MCP by default.
