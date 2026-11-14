"""
Export the pixel-art bike from media/bike.aseprite for the website.

    media/bike.gif           homepage header, black tires
    media/bike-flipped.gif   homepage header, facing the other way (non-drive side:
                             chain and chainring behind the frame)
    media/bike-tile.gif      links page background, teal tires, with transparent margins
    media/bike-tile.png      still frame of the tile, for people who turn off animations

The .aseprite file is never modified; tire colors etc. are applied only to the exports.
Edit the bike in Aseprite, then run:

    python utils/bike_gifs.py
"""

import os
import shutil
import subprocess
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SOURCE = os.path.join(ROOT_DIR, "media", "bike.aseprite")
LUA = os.path.join(ROOT_DIR, "utils", "bike_export.lua")

TAG = "pedal"  # the animation to export
STILL_FRAME = 4  # frame number (0-based) used for the still PNG: first frame of "pedal"

BLACK = {"tires": "#000000"}
TEAL = {"tires": "#2fae8f", "tire_hi": "#7fd9bf"}  # Simworks Homage-style green
TILE_PAD = "24,24,0,64"  # left,right,top,bottom margins: 64x64 bike -> 112x128 tile

EXPORTS = [
    ("media/bike.gif", dict(BLACK)),
    ("media/bike-flipped.gif", dict(BLACK, back="1")),
    ("media/bike-tile.gif", dict(TEAL, pad=TILE_PAD)),
    ("media/bike-tile.png", dict(TEAL, pad=TILE_PAD, still=True)),
]


def find_aseprite():
    for candidate in (
        shutil.which("aseprite"),
        r"C:\Program Files\Aseprite\Aseprite.exe",
        r"C:\Program Files (x86)\Steam\steamapps\common\Aseprite\Aseprite.exe",
        "/Applications/Aseprite.app/Contents/MacOS/aseprite",
    ):
        if candidate and os.path.exists(candidate):
            return candidate
    sys.exit("Aseprite not found; add it to PATH or edit find_aseprite() in this script")


def main():
    aseprite = find_aseprite()
    for out, opts in EXPORTS:
        opts = dict(opts)
        still = opts.pop("still", False)
        cmd = [aseprite, "-b", SOURCE]
        for k, v in opts.items():
            cmd += ["--script-param", f"{k}={v}"]
        cmd += ["--script", LUA]
        cmd += ["--frame-range", f"{STILL_FRAME},{STILL_FRAME}"] if still else ["--tag", TAG]
        cmd += ["--save-as", os.path.join(ROOT_DIR, out)]
        subprocess.run(cmd, check=True)
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
