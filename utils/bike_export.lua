-- Used by utils/bike_gifs.py: changes the open sprite in memory before it's exported.
-- Never saves the .aseprite file. Params (all optional):
--   tires=#rrggbb      tire color
--   tire_hi=#rrggbb    lighter color for the top edge of the tires (default: same as tires)
--   back=1             show the non-drive side: chain + chainring behind the frame, then flip
--   ring=#..,#..       chainring colors on the "frame" layer (default: #7f8891,#c3cad1)
--   pad=l,r,t,b        add transparent margins (pixels) around the canvas

local p = app.params
local spr = app.activeSprite
local pc = app.pixelColor

local function hex(s)
  return pc.rgba(tonumber(s:sub(2, 3), 16), tonumber(s:sub(4, 5), 16), tonumber(s:sub(6, 7), 16), 255)
end
local function key(v)
  return string.format("#%02x%02x%02x", pc.rgbaR(v), pc.rgbaG(v), pc.rgbaB(v))
end
local function layer(name)
  for _, l in ipairs(spr.layers) do
    if l.name == name then return l end
  end
  error("no layer named " .. name)
end

-- Tires: every tire pixel gets the base color; pixels with nothing above them get the highlight
if p.tires and p.tires ~= "" then
  local base = hex(p.tires)
  local hi = (p.tire_hi and p.tire_hi ~= "") and hex(p.tire_hi) or base
  for _, cel in ipairs(layer("tires").cels) do
    local img = cel.image
    local src = img:clone()
    for y = 0, img.height - 1 do
      for x = 0, img.width - 1 do
        if pc.rgbaA(src:getPixel(x, y)) > 0 then
          local top = (y == 0) or pc.rgbaA(src:getPixel(x, y - 1)) == 0
          img:drawPixel(x, y, top and hi or base)
        end
      end
    end
  end
end

-- Non-drive side: the chain and chainring are on the far side of the bike, so they go
-- behind the frame and wheels; the crank arm and pedal (drivetrain layer) stay in front.
if p.back == "1" then
  local ring_colors = {}
  for c in string.gmatch((p.ring and p.ring ~= "") and p.ring or "#7f8891,#c3cad1", "[^,]+") do
    ring_colors[c:lower()] = true
  end
  local frame_layer, chain_layer = layer("frame"), layer("chain")
  local ring_layer = spr:newLayer()
  ring_layer.name = "chainring-back"
  for _, cel in ipairs(frame_layer.cels) do
    local img = cel.image
    local ring = Image(img.width, img.height, img.colorMode)
    local moved = false
    for y = 0, img.height - 1 do
      for x = 0, img.width - 1 do
        local v = img:getPixel(x, y)
        if pc.rgbaA(v) > 0 and ring_colors[key(v)] then
          ring:drawPixel(x, y, v)
          img:drawPixel(x, y, pc.rgba(0, 0, 0, 0))
          moved = true
        end
      end
    end
    if moved then spr:newCel(ring_layer, cel.frameNumber, ring, cel.position) end
  end
  -- bottom to top: chain, chainring, spokes, tires, frame, drivetrain
  chain_layer.stackIndex = 1
  ring_layer.stackIndex = 2
  app.command.Flip{ target = "canvas", orientation = "horizontal" }
end

-- Transparent margins (for tiling)
if p.pad and p.pad ~= "" then
  local l, r, t, b = string.match(p.pad, "(%d+),(%d+),(%d+),(%d+)")
  app.command.CanvasSize{ ui = false, left = tonumber(l), right = tonumber(r), top = tonumber(t), bottom = tonumber(b), trimOutside = false }
end
