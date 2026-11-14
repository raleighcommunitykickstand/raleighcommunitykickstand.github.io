# utils — notes to future me

All of these run from the repo root (`python utils/<script>.py`) or from inside `utils/`.

## Where things live

| Folder | What | Published? |
|---|---|---|
| `_media/photos/` | Full-size photo originals | No (git-ignored, OneDrive only) |
| `_media/newsletter-images/` | Full-size newsletter originals | No (git-ignored, OneDrive only) |
| `_media/logos/` | Logo + badge `.ai` files | No |
| `media/` | Everything the site uses (photos, logos, docs, icons) | Yes |
| `newsletter/images/` | Email-ready newsletter images | Yes |

**Never rename or delete anything a sent email links to:** older files in `newsletter/images/`,
`media/RCK_logo-by.png`, `fonts/hwtartz.css` and the files it loads, and the newsletter `.html` pages.

## Writing a newsletter

1. Drop originals into `_media/newsletter-images/` with dated, dashed names (`2026-12-flyer.png`).
2. `python utils/convert_images.py` → resized `.jpg` (or `.png` if transparent) in `newsletter/images/`.
   Emails get JPG/PNG, not WebP — classic Outlook can't show WebP.
3. Write `newsletter/2026-12.md`, linking the copies: `![December Flyer](images/2026-12-flyer.jpg)`.
4. `python utils/md2mjml.py` → builds the newest issue (`.mjml` + `.html`) and updates `newsletters.js`.
   - `python utils/md2mjml.py 2026-12` builds one issue; `--all` rebuilds every issue (changes sent ones' web copies, so avoid).
   - It warns if the markdown uses `.webp` images.

Slideshow GIF from several images: `python utils/make_gif.py 2026-12-flyer` (matches every original
starting with that name; `--fade 6`, `--duration 3000`, `--width 600`, `-o name.gif`). Output goes to `newsletter/images/`.

## Website photos

1. Put originals in `_media/photos/`.
2. `python utils/convert_images.py` → resized `.webp` in `media/photos/`. Link the `.webp` in the HTML.
   Only new/changed originals convert; `--force` redoes everything.

`convert_images.py` strips **all** metadata from every copy it makes (camera/GPS EXIF, XMP, Canva/Adobe
"content credentials", text tags), after converting colors to sRGB. Originals in `_media/` keep theirs.
`logo_variants.py` writes metadata-free PNGs too.

## Logos

- `python utils/logo_variants.py` → every color version of the `logo-*.ai` files, plus black/white
  `badge-*.ai`, as SVG + PNG in `media/logos/`. `python utils/logo_variants.py logo-rck` does just matching ones.
- Colors are at the top of the script (`INKS`, `INNERS`, `INNERS_FOR_INK`).
- `.ai` files must be saved with **Create PDF Compatible File** checked, black shapes + white inner parts.
- Website: use the `.svg`. Email: use a `.png`.
- It also writes `<name>-outlined.ai` next to each `logo-*`/`badge-*` source in `_media/logos/`: same
  black/white artwork with the text turned into shapes, so it opens anywhere without HWT Artz installed
  (good for sending to printers/designers). Edit the original `.ai`, never the `-outlined` one — it gets overwritten.

## Pixel-art bike

`python utils/bike_gifs.py` → from `media/bike.aseprite`: black-tire `bike.gif` + `bike-flipped.gif`
(homepage) and teal-tire `bike-tile.gif/.png` (links page background). Tire colors are at the top of the script.
Never changes the `.aseprite` file. Needs Aseprite installed.

## Renaming files

`python utils/normalize_site_images.py --dry-run`, then `--git` to do it. Lowercases + dashes names in
`media/` (and the matching originals in `_media/photos/`) and fixes links in the site's HTML/CSS/JS.
Skips anything a sent newsletter links to.

## Checking for broken links

`python utils/check_links.py` → reports (never fixes) broken links in every page, CSS, JS, newsletter
`.md`/`.mjml`/`.html`, and the manifest: missing files, wrong upper/lowercase (fine on Windows, broken
on GitHub Pages), bad `#anchors`, and links into `_` folders that don't get published. Full URLs on
our own domain (read from `CNAME`) are checked against the local files — that covers the emails.

- `--external` also checks outside links (~1 min). "Refused" ones (403 etc.) usually work in a browser; open them by hand.
- Works on any other project: `python utils/check_links.py path/to/site` (`--site example.org` if there's no CNAME).
- Exits with code 1 when something's broken. Run it before pushing.

## Setup (new computer)

- Python: `pip install pillow pillow-heif fonttools beautifulsoup4 ftfy`
- Node (for md2mjml): `npm install mjml marked` in the repo root
- ImageMagick (`magick`) for logo PNGs; Aseprite for the bike
- Copy `_media/` over from OneDrive — the originals aren't in git.
