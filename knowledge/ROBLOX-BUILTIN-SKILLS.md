# Roblox's own built-in Assistant skills

Roblox currently documents these Roblox-authored skills:

- `rbx-create-skill`
- `rbx-debug`
- `rbx-device-simulator-lua`
- `rbx-docs-search`
- `rbx-perf-profiling`
- `rbx-scene-analysis`
- `rbx-unit-test`

Why RobloxForge cares:

The official Studio MCP can expose a `skill` capability. A weak external model can
delegate the specialized hard part to Roblox's own maintained workflow instead of
inventing a debugger/device/perf workflow.

Always discover current skill/tool availability at runtime.

Source:
https://github.com/Roblox/creator-docs/blob/main/content/en-us/assistant/skills.md
