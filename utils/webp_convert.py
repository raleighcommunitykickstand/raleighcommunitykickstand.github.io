import argparse
import os
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

# Enable HEIC/HEIF support for Pillow
register_heif_opener()

# This script lives in utils/; folders are relative to the repo root.
# Each image's .webp is written next to it in the same folder.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
FOLDERS = ["newsletter/images", "photos", "media"]

# Emails show images at most 560px wide and the site's photo columns are about as wide;
# 1200px stays sharp on 2x phone/retina screens.
# Quality 80 looks essentially identical at that size and is 6-30x smaller than q100 full-size.
# After changing these, run with --force so existing .webp files are regenerated.
# Browser/phone icons must stay PNG/ICO, so never make .webp copies of them.
# Matched against the start of the file name, ignoring case.
SKIP_PREFIXES = ("favicon", "apple-touch-icon", "web-app-manifest", "android-chrome", "mstile")

QUALITY = 80
MAX_SIZE = (1200, 1600)  # fit within this box (keeps aspect ratio, never enlarges); None = keep full size


def convert_to_webp(input_path, output_path):
    with Image.open(input_path) as img:
        img = ImageOps.exif_transpose(img)

        if img.mode in ("RGBA", "LA") or "transparency" in img.info:
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")

        if MAX_SIZE:
            img.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)

        img.save(output_path, "WEBP", quality=QUALITY, method=6, optimize=True)


def is_up_to_date(input_path, output_path):
    """True if the .webp exists and is newer than the original it came from."""
    return os.path.exists(output_path) and os.path.getmtime(output_path) >= os.path.getmtime(input_path)


def convert_images(input_dir, output_dir, force=False):
    seen_outputs = set()
    converted = skipped = 0

    for filename in os.listdir(input_dir):
        if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".heic", ".heif")):
            continue

        if filename.lower().startswith(SKIP_PREFIXES):
            continue

        input_path = os.path.join(input_dir, filename)
        original_name, _ = os.path.splitext(filename)

        output_filename = f"{original_name}.webp"
        output_path = os.path.join(output_dir, output_filename)

        if output_filename in seen_outputs:
            print(f"Skipping {filename}: " f"duplicate normalized name -> {output_filename}")
            continue

        seen_outputs.add(output_filename)

        # Only convert new originals, or originals edited since their .webp was made
        if not force and is_up_to_date(input_path, output_path):
            skipped += 1
            continue

        # "->" not an arrow character: the Windows console can't print it when output is piped
        print(f"  Converting: {filename} -> {output_filename}")

        try:
            convert_to_webp(input_path, output_path)
            converted += 1
        except Exception as e:
            print(f"  ERROR converting {filename}: {e}")

    print(f"  {converted} converted, {skipped} already up to date.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert new or changed images to .webp, next to the originals.")
    parser.add_argument(
        "folders",
        nargs="*",
        default=FOLDERS,
        help=f"folders to convert, relative to the repo root (default: {' '.join(FOLDERS)})",
    )
    parser.add_argument("--force", action="store_true", help="reconvert every image, even if its .webp is up to date")
    args = parser.parse_args()

    for folder in args.folders:
        path = os.path.join(ROOT_DIR, folder)
        if not os.path.isdir(path):
            print(f"{folder}/: not found, skipping")
            continue
        print(f"{folder}/")
        convert_images(path, path, force=args.force)
