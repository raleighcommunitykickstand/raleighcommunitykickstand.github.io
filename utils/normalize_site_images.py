"""
Lowercase + dash-ify file names in media/ (and all its subfolders) and update every link to
them in the website's HTML, JS, CSS, and manifest files.

The originals in _media/photos/ are renamed the same way, so they keep matching their .webp
in media/photos/ (otherwise utils/convert_images.py would recreate the old .webp name).

    IMG_3451.jpg                  -> img-3451.jpg
    sherri larry transparent.png  -> sherri-larry-transparent.png

Files linked from newsletter/ are never renamed: those newsletters were emailed, and the
emails load the files by absolute URL (e.g. media/RCK_logo-by.png in every header).

Run a dry run first:
    python utils/normalize_site_images.py --dry-run
Then for real (use --git so case-only renames are seen by git on Windows):
    python utils/normalize_site_images.py --git
"""

import argparse
import os
import re
import subprocess
import sys
from urllib.parse import quote

# This script lives in utils/; everything is relative to the repo root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# media/ and every folder inside it. Deepest first, so a link like media/photos/x.webp
# matches media/photos, not media.
MEDIA_DIR = "media"
FOLDERS = sorted(
    (os.path.relpath(dp, ROOT_DIR).replace("\\", "/") for dp, _, _ in os.walk(os.path.join(ROOT_DIR, MEDIA_DIR))),
    key=lambda f: (-f.count("/"), f),
)
# Unpublished photo originals: renamed alongside media/photos so convert_images keeps matching names
FOLDERS.append("_media/photos")

# Files whose links get updated
TEXT_EXTS = (".html", ".htm", ".js", ".mjs", ".css", ".json", ".webmanifest", ".xml", ".md", ".txt", ".yml")

# Never edited. newsletter/ is the emailed newsletters; it is only scanned for protected files.
SKIP_DIRS = {".git", "node_modules", "bootstrap", "fonts", "newsletter", "utils", "_media"}

NEWSLETTER_DIR = os.path.join(ROOT_DIR, "newsletter")


def normalize(name):
    return re.sub(r"[_\s]+", "-", name).lower()


def ref_pattern(folder, name):
    """Regex for folder/name in a link: plain, with %20 for spaces, any case, whole name only."""
    variants = {name, quote(name), name.replace(" ", "%20")}
    alts = "|".join(re.escape(v) for v in sorted(variants, key=len, reverse=True))
    return re.compile(rf"(?<![\w-])({re.escape(folder)}/)({alts})(?![\w.%-])", re.IGNORECASE)


def iter_text_files(top, skip_dirs):
    for dirpath, dirnames, filenames in os.walk(top):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for f in filenames:
            if f.lower().endswith(TEXT_EXTS):
                yield os.path.join(dirpath, f)


def read_text(path):
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            return fh.read()
    except UnicodeDecodeError:
        print(f"  WARNING: skipping {os.path.relpath(path, ROOT_DIR)} (not UTF-8)")
        return None


def protected_files():
    """Files in photos/ or media/ that any newsletter links to."""
    protected = set()  # (folder, lowercase name)
    pattern = re.compile(r"(?<![\w-])(" + "|".join(FOLDERS) + r")/([^\"'()<>?#\n]+?\.\w{2,12})(?![\w.])", re.IGNORECASE)
    for dirpath, _, filenames in os.walk(NEWSLETTER_DIR):
        for f in filenames:
            if not f.lower().endswith((".html", ".mjml", ".md")):
                continue
            text = read_text(os.path.join(dirpath, f)) or ""
            for folder, name in pattern.findall(text):
                # Protect by base name, so RCK_logo-by.png also keeps its RCK_logo-by.webp copy
                # (renaming only the .webp would make convert_images recreate the old name)
                base = os.path.splitext(name.replace("%20", " "))[0]
                protected.add((folder.lower(), base.lower()))
    return protected


def git_case_duplicates(folder):
    """Names git tracks twice with different case (e.g. IMG_2719.JPG and IMG_2719.jpg)."""
    r = subprocess.run(["git", "ls-files", folder], cwd=ROOT_DIR, capture_output=True, text=True)
    seen, dupes = {}, set()
    for path in r.stdout.splitlines():
        name = path[len(folder) + 1 :]
        if "/" in name:
            continue  # only files directly in the folder
        if name.lower() in seen and seen[name.lower()] != name:
            dupes.add(name.lower())
        seen[name.lower()] = name
    return dupes


def plan_renames(protected):
    renames = []  # (folder, old, new)
    for folder in FOLDERS:
        folder_path = os.path.join(ROOT_DIR, folder)
        if not os.path.isdir(folder_path):
            continue
        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        existing_lower = {f.lower(): f for f in files}
        dupes = git_case_duplicates(folder)
        claimed = {}

        for old in sorted(files):
            new = normalize(old)
            if new == old:
                continue
            if (folder, os.path.splitext(old)[0].lower()) in protected:
                print(f"  KEEP {folder}/{old}: linked from a sent newsletter")
                continue
            if old.lower() in dupes:
                print(f"  SKIP {folder}/{old}: git tracks this name twice with different case; fix that first")
                continue
            clash = existing_lower.get(new.lower())
            if clash and clash.lower() != old.lower():
                print(f"  SKIP {folder}/{old}: {new} already exists")
                continue
            if new in claimed:
                print(f"  SKIP {folder}/{old}: {claimed[new]} also becomes {new}")
                continue
            claimed[new] = old
            renames.append((folder, old, new))
    return renames


def is_tracked(path):
    r = subprocess.run(["git", "ls-files", "--error-unmatch", path], cwd=ROOT_DIR, capture_output=True)
    return r.returncode == 0


def do_rename(folder, old, new, use_git):
    src = os.path.join(ROOT_DIR, folder, old)
    dst = os.path.join(ROOT_DIR, folder, new)
    tmp = dst + ".renametmp"
    case_only = old.lower() == new.lower()

    if use_git and is_tracked(src):
        if case_only:
            subprocess.run(["git", "mv", src, tmp], check=True, cwd=ROOT_DIR)
            subprocess.run(["git", "mv", tmp, dst], check=True, cwd=ROOT_DIR)
        else:
            subprocess.run(["git", "mv", src, dst], check=True, cwd=ROOT_DIR)
    else:
        if case_only:
            os.rename(src, tmp)
            os.rename(tmp, dst)
        else:
            os.rename(src, dst)


def update_links(renames, dry_run):
    patterns = [(ref_pattern(folder, old), new) for folder, old, new in renames]
    total = 0

    for path in sorted(iter_text_files(ROOT_DIR, SKIP_DIRS)):
        text = read_text(path)
        if text is None:
            continue

        changes = []
        new_text = text
        for pattern, new in patterns:
            def repl(m, new=new):
                changes.append((m.group(0), m.group(1) + new))
                return m.group(1) + new

            new_text = pattern.sub(repl, new_text)

        if changes:
            total += len(changes)
            print(f"\n  {os.path.relpath(path, ROOT_DIR)}: {len(changes)} link(s)")
            for a, b in changes:
                print(f"    {a}  ->  {b}")
            if not dry_run:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new_text)

    return total


def report_broken_links():
    """Links into photos/ or media/ that don't match any file on disk (exact case, like GitHub Pages)."""
    on_disk = {f: set(os.listdir(os.path.join(ROOT_DIR, f))) for f in FOLDERS if os.path.isdir(os.path.join(ROOT_DIR, f))}
    pattern = re.compile(r"(?<![\w-])(" + "|".join(FOLDERS) + r")/([^\"'()<>?#\n]+?\.\w{2,12})(?![\w.])")
    broken = []
    for path in iter_text_files(ROOT_DIR, SKIP_DIRS):
        text = read_text(path) or ""
        for folder, name in pattern.findall(text):
            name = name.replace("%20", " ")
            if "/" not in name and name not in on_disk.get(folder, set()):
                broken.append((os.path.relpath(path, ROOT_DIR), f"{folder}/{name}"))
    return broken


def main():
    p = argparse.ArgumentParser(description="Lowercase + dash-ify photos/ and media/ file names and fix links.")
    p.add_argument("--dry-run", action="store_true", help="show what would change, change nothing")
    p.add_argument("--git", action="store_true", help="rename with 'git mv' so git sees case-only renames")
    args = p.parse_args()

    tag = "[DRY RUN] " if args.dry_run else ""

    protected = protected_files()
    print(f"{tag}Planning renames in {', '.join(f + '/' for f in FOLDERS)}")
    renames = plan_renames(protected)

    for folder, old, new in renames:
        print(f"  {folder}/{old}  ->  {folder}/{new}")
        if not args.dry_run:
            do_rename(folder, old, new, args.git)
    print(f"{tag}{len(renames)} file(s) renamed.")

    print(f"\n{tag}Updating links (skipping {', '.join(sorted(SKIP_DIRS))})")
    total = update_links(renames, args.dry_run)
    print(f"\n{tag}{total} link(s) updated.")

    broken = report_broken_links()
    if broken:
        when = "currently " if args.dry_run else ""
        print(f"\nWARNING: these links {when}don't match a file on disk (GitHub Pages is case-sensitive):")
        for where, ref in broken:
            print(f"  {where}: {ref}")

    print("\nNote: links built in code (e.g. 'photos/' + name) can't be found automatically.")


if __name__ == "__main__":
    main()
