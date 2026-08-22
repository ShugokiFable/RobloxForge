--!strict

local Players = game:GetService("Players")

local function onPlayerAdded(player: Player)
	-- Start with the smallest server-authoritative gameplay slice.
end

Players.PlayerAdded:Connect(onPlayerAdded)

for _, player in Players:GetPlayers() do
	task.spawn(onPlayerAdded, player)
end
