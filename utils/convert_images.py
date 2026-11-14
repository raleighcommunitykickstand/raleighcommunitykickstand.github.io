"""
Make web-ready copies of new or changed images, resized to fit 1200x1600.

    _media/photos/            -> media/photos/      .webp  (website: every browser supports it)
    _media/newsletter-images/ -> newsletter/images/ .jpg, or .png if the image has transparency
                                                    (email: classic Outlook for Windows and some
                                                    other email apps can't show .webp)

Every copy is stripped of ALL metadata (EXIF incl. camera/GPS, XMP, Canva/Adobe content
credentials, text tags). Colors are first converted from the original's color profile to
standard sRGB, so stripping the profile doesn't shift colors.

Originals stay in _media/ (not published). Newsletter images from before EMAIL_FORMAT_SINCE
are skipped: those issues were already emailed with their .webp copies, which must not change.

    python utils/convert_images.py           # only new or changed originals
    python utils/convert_images.py --force   # redo everything (e.g. after changing quality)
"""

import argparse
import io
import os
import re

from PIL import Image, ImageCms, ImageOps
from pillow_heif import register_heif_opener

# Enable HEIC/HEIF support for Pillow
register_heif_opener()

# This script lives in utils/; folders are relative to the repo root.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
FOLDERS = [
    # (originals, output, format)  format: "webp" or "email" (jpg/png)
    ("_media/photos", "media/photos", "webp"),
    ("_media/newsletter-images", "newsletter/images", "email"),
]

# Emails show images at most 560px wide and the site's photo columns are about as wide;
# 1200px stays sharp on 2x phone/retina screens. Only files directly in each originals
# folder are converted, never subfolders.
MAX_SIZE = (1200, 1600)  # fit within this box (keeps aspect ratio, never enlarges); None = keep full size
WEBP_QUALITY = 80  # looks essentially identical at this size
JPEG_QUALITY = 82  # about the same file size as WebP 80 for flyers, a bit bigger for photos

# Newsletters dated before this (year, month) were sent with .webp images: don't make email copies
EMAIL_FORMAT_SINCE = (2026, 12)
DATE_PREFIX = re.compile(r"(\d{4})(?:[-_](\d{2})(?!\d))?")

ORIGINAL_EXTS = (".png", ".jpg", ".jpeg", ".heic", ".heif")


def sent_before_switch(filename):
    m = DATE_PREFIX.match(filename)
    if not m:
        return False
    return (int(m.group(1)), int(m.group(2) or 0)) < EMAIL_FORMAT_SINCE


SRGB = ImageCms.createProfile("sRGB")


def to_srgb(img):
    """Convert pixels from the image's embedded color profile (e.g. iPhone Display P3) to sRGB."""
    icc = img.info.get("icc_profile")
    if not icc:
        return img
    try:
        src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        return ImageCms.profileToProfile(img, src, SRGB, outputMode=img.mode)
    except Exception:
        return img  # unreadable profile: keep pixels as-is


def strip_metadata(img):
    """A brand-new image holding only the pixels: no EXIF, XMP, ICC, text, or content credentials."""
    clean = Image.frombytes(img.mode, img.size, img.tobytes())
    return clean


def load(input_path):
    """Open, rotate per EXIF, convert to sRGB, resize, strip metadata. Returns (image, has_transparency)."""
    with Image.open(input_path) as img:
        img = ImageOps.exif_transpose(img)
        icc = img.info.get("icc_profile")
        if img.mode in ("RGBA", "LA", "P") or "transparency" in img.info:
            img = img.convert("RGBA")
            transparent = img.getchannel("A").getextrema()[0] < 255
            if not transparent:
                img = img.convert("RGB")
        else:
            img = img.convert("RGB")
            transparent = False
        if icc:
            img.info["icc_profile"] = icc
            img = to_srgb(img)
        if MAX_SIZE:
            img.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)
        return strip_metadata(img), transparent


def output_name(original_name, fmt, transparent):
    if fmt == "webp":
        return original_name + ".webp"
    return original_name + (".png" if transparent else ".jpg")


def save(img, output_path):
    # No exif/icc_profile/xmp/pnginfo arguments are passed, and the image has no info of its
    # own (see strip_metadata), so nothing but pixels is written.
    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".webp":
        img.save(output_path, "WEBP", quality=WEBP_QUALITY, method=6)
    elif ext == ".png":
        img.save(output_path, "PNG", optimize=True)
    else:
        img.save(output_path, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)


def is_up_to_date(input_path, output_path):
    """True if the copy exists and is newer than the original it came from."""
    return os.path.exists(output_path) and os.path.getmtime(output_path) >= os.path.getmtime(input_path)


def guess_transparency(input_path):
    """Cheap check (no resize) used to work out the output name before deciding to convert."""
    with Image.open(input_path) as img:
        if img.mode in ("RGBA", "LA", "P") or "transparency" in img.info:
            return img.convert("RGBA").getchannel("A").getextrema()[0] < 255
    return False


def convert_images(input_dir, output_dir, fmt, force=False):
    seen_outputs = set()
    converted = skipped = 0

    for filename in sorted(os.listdir(input_dir)):
        if not filename.lower().endswith(ORIGINAL_EXTS):
            continue
        if fmt == "email" and sent_before_switch(filename):
            continue  # already-sent newsletter: keep its existing .webp only

        input_path = os.path.join(input_dir, filename)
        original_name = os.path.splitext(filename)[0]
        transparent = guess_transparency(input_path) if fmt == "email" else False
        output_filename = output_name(original_name, fmt, transparent)
        output_path = os.path.join(output_dir, output_filename)

        if output_filename in seen_outputs:
            print(f"  Skipping {filename}: another original also becomes {output_filename}")
            continue
        seen_outputs.add(output_filename)

        # Only convert new originals, or originals edited since their copy was made
        if not force and is_up_to_date(input_path, output_path):
            skipped += 1
            continue

        # "->" not an arrow character: the Windows console can't print it when output is piped
        print(f"  Converting: {filename} -> {output_filename}")
        try:
            img, _ = load(input_path)
            save(img, output_path)
            converted += 1
        except Exception as e:
            print(f"  ERROR converting {filename}: {e}")

    print(f"  {converted} converted, {skipped} already up to date.")


def main():
    parser = argparse.ArgumentParser(description="Make resized, metadata-free web/email copies of new or changed images.")
    parser.add_argument("--force", action="store_true", help="reconvert every image, even if its copy is up to date")
    args = parser.parse_args()

    for src, dst, fmt in FOLDERS:
        src_path = os.path.join(ROOT_DIR, src)
        dst_path = os.path.join(ROOT_DIR, dst)
        if not os.path.isdir(src_path):
            print(f"{src}/: not found, skipping")
            continue
        os.makedirs(dst_path, exist_ok=True)
        print(f"{src}/ -> {dst}/ ({'webp' if fmt == 'webp' else 'jpg/png for email'})")
        convert_images(src_path, dst_path, fmt, force=args.force)


if __name__ == "__main__":
    main()
