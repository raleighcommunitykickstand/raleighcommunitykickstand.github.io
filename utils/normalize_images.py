import argparse
import os
import re
import subprocess
import sys

# This script lives in utils/; BASE_DIR is the newsletter/ folder it works on
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
BASE_DIR = os.path.join(ROOT_DIR, "newsletter")
IMAGES_DIR = os.path.join(BASE_DIR, "images")

# Matches images/<filename> inside ![alt](images/x.webp), src="images/x.webp", etc.
IMAGE_REF = re.compile(r"(images/)([^)\s\"'>]+)")


# Images from newsletters before this month were already emailed and are linked by
# absolute URL from people's inboxes. Never rename them or those emails break.
CUTOFF = (2026, 11)
DATE_PREFIX = re.compile(r"(\d{4})(?:[-_](\d{2})(?!\d))?")


def is_protected(name):
    m = DATE_PREFIX.match(name)
    if not m:
        return False
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else 0  # year-only names like 2025_annual
    return (year, month) < CUTOFF


def normalize(name):
    return name.replace("_", "-").lower()


def plan_renames():
    files = [f for f in os.listdir(IMAGES_DIR) if os.path.isfile(os.path.join(IMAGES_DIR, f))]
    existing_lower = {f.lower(): f for f in files}

    renames = {}  # old -> new
    claimed = {}  # new (lower) -> old, to catch two files mapping to the same name
    for old in sorted(files):
        if is_protected(old):
            continue
        new = normalize(old)
        if new == old:
            continue
        clash = existing_lower.get(new.lower())
        if clash and clash.lower() != old.lower():
            print(f"  SKIP {old}: {new} already exists ({clash})")
            continue
        if new in claimed:
            print(f"  SKIP {old}: {claimed[new]} also becomes {new}")
            continue
        claimed[new] = old
        renames[old] = new
    return renames, files


def is_tracked(path):
    r = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path],
        cwd=BASE_DIR,
        capture_output=True,
    )
    return r.returncode == 0


def do_rename(old, new, use_git):
    src = os.path.join(IMAGES_DIR, old)
    dst = os.path.join(IMAGES_DIR, new)
    case_only = old.lower() == new.lower()

    if use_git and is_tracked(src):
        if case_only:
            tmp = os.path.join(IMAGES_DIR, new + ".renametmp")
            subprocess.run(["git", "mv", src, tmp], check=True, cwd=BASE_DIR)
            subprocess.run(["git", "mv", tmp, dst], check=True, cwd=BASE_DIR)
        else:
            subprocess.run(["git", "mv", src, dst], check=True, cwd=BASE_DIR)
    else:
        if case_only:
            tmp = dst + ".renametmp"
            os.rename(src, tmp)
            os.rename(tmp, dst)
        else:
            os.rename(src, dst)


def update_markdown(renames, all_files, dry_run):
    # Final name of every file on disk, looked up case-insensitively
    final_name = {f.lower(): renames.get(f, f) for f in all_files}

    md_files = [f for f in os.listdir(BASE_DIR) if f.lower().endswith(".md")]
    total = 0
    missing = []

    for md in sorted(md_files):
        path = os.path.join(BASE_DIR, md)
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()

        changes = []

        def repl(m):
            ref = m.group(2)
            if "/" in ref:  # subfolder: leave alone
                return m.group(0)
            target = final_name.get(ref.lower())
            if target is None:
                # File may already have been renamed on an earlier run
                target = final_name.get(normalize(ref))
            if target is None:
                missing.append((md, ref))
                return m.group(0)
            if target != ref:
                changes.append((ref, target))
                return m.group(1) + target
            return m.group(0)

        new_text = IMAGE_REF.sub(repl, text)

        if changes:
            total += len(changes)
            print(f"\n  {md}: {len(changes)} reference(s)")
            for a, b in changes:
                print(f"    images/{a}  ->  images/{b}")
            if not dry_run:
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new_text)

    return total, missing


def main():
    p = argparse.ArgumentParser(description="Lowercase + dash-ify image names and fix .md references.")
    p.add_argument("--dry-run", action="store_true", help="show what would change, change nothing")
    p.add_argument("--git", action="store_true", help="rename with 'git mv' so git sees case-only renames")
    args = p.parse_args()

    if not os.path.isdir(IMAGES_DIR):
        sys.exit(f"No images folder at {IMAGES_DIR}")

    tag = "[DRY RUN] " if args.dry_run else ""
    print(f"{tag}Planning renames in {IMAGES_DIR}")
    renames, all_files = plan_renames()

    for old, new in renames.items():
        print(f"  {old}  ->  {new}")
        if not args.dry_run:
            do_rename(old, new, args.git)
    print(f"{tag}{len(renames)} file(s) renamed.")

    print(f"\n{tag}Updating .md files in {BASE_DIR}")
    total, missing = update_markdown(renames, all_files, args.dry_run)
    print(f"\n{tag}{total} reference(s) updated.")

    if missing:
        print("\nWARNING: these references point to files that don't exist in images/:")
        for md, ref in missing:
            print(f"  {md}: images/{ref}")


if __name__ == "__main__":
    main()
