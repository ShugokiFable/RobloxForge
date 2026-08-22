# Current Roblox toolchain snapshot — researched 2026-08-22

This is a **recommendation snapshot**, not an auto-install list.

| Tool | Snapshot | Why |
|---|---:|---|
| Rojo | 7.7.0 | source-controlled Roblox projects |
| Rokit | 1.2.0 | maintained toolchain manager |
| StyLua | 2.5.2 | formatter |
| Selene | 0.31.0 | linter |
| luau-lsp | 1.69.0 | Roblox-aware LSP/sourcemaps |
| Wally | 0.3.2 | packages |
| Lune | 0.10.5 | standalone Luau/Roblox data |
| run-in-roblox | 0.3.0 | run place/scripts in Studio from CLI |
| wally-package-types | 1.6.2 | types for Wally packages |

## Important

- Prefer Rokit over Aftman for new projects; Aftman is archived.
- Do not use Rojo just because the game is Roblox. Studio-native workflows are valid.
- Do not install every tool for a blank-place prototype.
- Recheck releases before creating a new lockfile/pin.
