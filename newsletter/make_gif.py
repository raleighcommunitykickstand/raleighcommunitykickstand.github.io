import argparse
import os
import re
import sys

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "images/")
OUTPUT_DIR = INPUT_DIR

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".heic", ".heif", ".webp")


def natural_key(name):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def find_matches(prefix, input_dir):
    files = [
        f for f in os.listdir(input_dir) if f.lower().startswith(prefix.lower()) and f.lower().endswith(IMAGE_EXTS)
    ]
    # If both photo.heic and photo.webp exist, keep only one per base name
    by_base = {}
    for f in sorted(files, key=natural_key):
        base = os.path.splitext(f)[0]
        by_base.setdefault(base, f)
    return sorted(by_base.values(), key=natural_key)


def load_rgb(path):
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA") or "transparency" in img.info:
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.getchannel("A"))
            return bg
        return img.convert("RGB")


def fit_to_canvas(img, size, crop, bg):
    if crop:
        # Fill the whole canvas, cropping edges if aspect ratios differ
        return ImageOps.fit(img, size, Image.Resampling.LANCZOS)
    # Fit inside the canvas, letterboxing with the background color
    img = ImageOps.contain(img, size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, bg)
    canvas.paste(img, ((size[0] - img.width) // 2, (size[1] - img.height) // 2))
    return canvas


def to_gif_frame(img):
    # Per-frame adaptive 256-color palette + Floyd-Steinberg dithering = best GIF quality
    return img.quantize(
        colors=256,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.FLOYDSTEINBERG,
    )


def main():
    p = argparse.ArgumentParser(description="Make a GIF slideshow from images matching a prefix.")
    p.add_argument("prefix", help="filename prefix to match, e.g. 'ride' matches ride1.jpg, ride_2.heic")
    p.add_argument("--width", type=int, default=600, help="output width in px (default 600, good for email)")
    p.add_argument("--height", type=int, default=None, help="output height (default: from first image's aspect)")
    p.add_argument("--duration", type=int, default=2500, help="ms each image is shown (default 2500)")
    p.add_argument("--fade", type=int, default=0, help="number of crossfade frames between images (e.g. 6)")
    p.add_argument("--fade-ms", type=int, default=60, help="ms per crossfade frame (default 60)")
    p.add_argument("--crop", action="store_true", help="crop to fill canvas instead of letterboxing")
    p.add_argument("--bg", default="#ffffff", help="letterbox background color (default white)")
    p.add_argument("--no-loop", action="store_true", help="play once instead of looping forever")
    p.add_argument("-o", "--output", default=None, help="output filename (default <prefix>.gif)")
    args = p.parse_args()

    files = find_matches(args.prefix, INPUT_DIR)
    if not files:
        sys.exit(f"No images in {INPUT_DIR} start with '{args.prefix}'.")

    print(f"Found {len(files)} image(s):")
    for f in files:
        print(f"  {f}")

    images = [load_rgb(os.path.join(INPUT_DIR, f)) for f in files]

    if args.height:
        size = (args.width, args.height)
    else:
        first = images[0]
        size = (args.width, round(args.width * first.height / first.width))

    slides = [fit_to_canvas(img, size, args.crop, args.bg) for img in images]

    frames, durations = [], []
    n = len(slides)
    for i, slide in enumerate(slides):
        frames.append(slide)
        durations.append(args.duration)
        if args.fade > 0 and n > 1 and (i < n - 1 or not args.no_loop):
            nxt = slides[(i + 1) % n]
            for k in range(1, args.fade + 1):
                frames.append(Image.blend(slide, nxt, k / (args.fade + 1)))
                durations.append(args.fade_ms)

    gif_frames = [to_gif_frame(f) for f in frames]

    out_name = args.output or f"{args.prefix}.gif"
    out_path = os.path.join(OUTPUT_DIR, out_name)

    save_kwargs = dict(
        save_all=True,
        append_images=gif_frames[1:],
        duration=durations,
        disposal=1,
        optimize=False,  # keep each frame's own palette intact
    )
    if not args.no_loop:
        save_kwargs["loop"] = 0

    gif_frames[0].save(out_path, **save_kwargs)

    size_kb = os.path.getsize(out_path) / 1024
    print(f"Wrote {out_path}  ({size[0]}x{size[1]}, {len(gif_frames)} frames, {size_kb:,.0f} KB)")


if __name__ == "__main__":
    main()
