"""Scaffold a new project from a genre template.

Writes the minimal sane layout (see skills references/architecture.md):
server systems module, shared config, client HUD stub, verification
checklist. Studio-native projects get .server/.client/.lua naming that
Rojo understands too.
"""
import os

from .errors import ForgeError

_SERVER = '''--!strict
-- Server entry point. Systems own authoritative state.
local Systems = game:GetService("ServerScriptService"):WaitForChild("Systems")

local Config = require(game:GetService("ReplicatedStorage"):WaitForChild("Config"))

print("[server] booted with genre=" .. Config.Genre)
'''

_CLIENT = '''--!strict
-- Client presentation. Listens to state; owns no truth.
local Players = game:GetService("Players")
local player = Players.LocalPlayer

local hud = Instance.new("ScreenGui")
hud.Name = "Hud"
hud.ResetOnSpawn = false
hud.Parent = player:WaitForChild("PlayerGui")

local label = Instance.new("TextLabel")
label.Size = UDim2.fromOffset(200, 40)
label.Position = UDim2.fromOffset(16, 16)
label.BackgroundTransparency = 0.4
label.TextColor3 = Color3.new(1, 1, 1)
label.Text = "Ready"
label.Parent = hud
'''

_CONFIG = '''--!strict
-- Shared contracts/config. Required by both sides.
return {
	Genre = "{genre}",
	Version = "0.1.0",
}
'''

_CHECKLIST = """# Verification checklist ({genre})

Slice 1 is DONE only when every box below has real evidence:
- [ ] player spawns
- [ ] core action works end-to-end (playtested)
- [ ] progression step works
- [ ] failure/death behavior works
- [ ] console clean during all of the above
- [ ] screenshot captured AND inspected
- [ ] rb_verify_receipt written

Expand only after proof.
"""


def scaffold(path, genre="generic"):
    genre = (genre or "generic").lower()
    if genre not in ("generic", "obby", "simulator", "tycoon"):
        raise ForgeError("RBF-ARG-001", "unknown genre %r" % genre,
                         hint="one of: generic, obby, simulator, tycoon")
    if os.path.isdir(path) and os.listdir(path):
        raise ForgeError("RBF-ARG-002", "target not empty: %r" % path,
                         hint="scaffold into a fresh directory")
    dirs = {
        os.path.join(path, "src", "server"): None,
        os.path.join(path, "src", "shared"): None,
        os.path.join(path, "src", "client"): None,
    }
    files = {
        os.path.join(path, "src", "server", "Main.server.lua"): _SERVER,
        os.path.join(path, "src", "shared", "Config.lua"): _CONFIG,
        os.path.join(path, "src", "client", "Hud.client.lua"): _CLIENT,
        os.path.join(path, "VERIFY.md"): _CHECKLIST,
    }
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    for f, content in files.items():
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(content.replace("{genre}", genre))
    return {"path": os.path.abspath(path), "genre": genre,
            "files": sorted(os.path.relpath(f, path).replace("\\\\", "/") for f in files),
            "next": "open Studio with a Baseplate, then follow VERIFY.md slice order"}
