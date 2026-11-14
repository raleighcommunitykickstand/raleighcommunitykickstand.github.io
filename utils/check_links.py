"""
Report broken links in a static website / email project. Reports only; never changes files.

Scans .html .htm .mjml .md .css .js .mjs .json .webmanifest .xml files and checks every link
to an image, stylesheet, script, font, document, or page:

  - local paths (relative, root-relative "/x", and full URLs on the site's own domain)
  - exact upper/lowercase (works on Windows/Mac but breaks on Linux hosts like GitHub Pages)
  - #anchors that point at an id that doesn't exist
  - links into folders the host won't publish (GitHub Pages/Jekyll skips "_" folders)
  - optionally, external links (--external)

Works on any project:

    python utils/check_links.py                       # this repo (the folder above utils/)
    python utils/check_links.py path/to/other/site    # any other project
    python utils/check_links.py --external            # also check outside links (slower)
    python utils/check_links.py --site example.org    # treat https://example.org/... as local files

The site's domain is read from a GitHub Pages CNAME file if there is one.
Exit code is 1 when problems are found (handy for automation).
"""

import argparse
import concurrent.futures
import os
import posixpath
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from urllib.parse import unquote, urldefrag, urlparse

SCAN_EXTS = (".html", ".htm", ".mjml", ".md", ".css", ".js", ".mjs", ".json", ".webmanifest", ".xml")
ALWAYS_SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".idea", ".vscode"}
IGNORE_PREFIXES = ("mailto:", "tel:", "sms:", "javascript:", "data:", "blob:", "about:")
IGNORE_EXACT = {"#", "#top", "#0"}  # common "go nowhere / back to top" links
# Things that look like links in JS strings: a path with a known file extension
ASSET_EXTS = ("html", "htm", "css", "js", "mjs", "json", "png", "jpg", "jpeg", "gif", "webp", "svg", "avif", "ico",
              "pdf", "ics", "woff", "woff2", "ttf", "otf", "eot", "mp4", "webm", "mp3", "txt", "xml", "webmanifest")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

ATTR_LINK = re.compile(r"""\b(src|href|poster|data-src|action|content|srcset|data-srcset)\s*=\s*(["'])(.*?)\2""", re.I | re.S)
CSS_URL = re.compile(r"""url\(\s*(["']?)([^"')]+)\1\s*\)|@import\s+(["'])([^"']+)\3""", re.I)
MD_LINK = re.compile(r"""!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+["'][^"']*["'])?\s*\)""")
JSON_LINK = re.compile(r'''"(?:src|href|url|start_url|icon)"\s*:\s*"([^"]+)"''', re.I)
JS_STRING = re.compile(r"""(["'`])((?:https?://|\.{0,2}/)?[\w@./%+-]+\.(?:""" + "|".join(ASSET_EXTS) + r"""))(?:[?#][^"'`]*)?\1""", re.I)
ID_ATTR = re.compile(r"""\b(?:id|name)\s*=\s*["']([^"']+)["']""", re.I)
COMMENT = {"html": re.compile(r"<!--.*?-->", re.S), "css": re.compile(r"/\*.*?\*/", re.S)}


class Checker:
    def __init__(self, root, site, skip, include_unpublished):
        self.root = os.path.abspath(root)
        self.site = site
        self.skip = ALWAYS_SKIP | set(skip)
        self.jekyll = not os.path.exists(os.path.join(self.root, ".nojekyll"))
        self.include_unpublished = include_unpublished
        self.problems = defaultdict(list)  # source file -> [(line, link, problem)]
        self.external = defaultdict(set)  # url -> {(file, line)}
        self.checked = 0
        self._listing = {}
        self._ids = {}

    # ---------- helpers
    def rel(self, path):
        return os.path.relpath(path, self.root).replace("\\", "/")

    def unpublished(self, rel_path):
        """GitHub Pages (Jekyll) doesn't publish folders/files starting with '_' unless .nojekyll exists."""
        return self.jekyll and any(part.startswith("_") for part in rel_path.split("/"))

    def listdir(self, d):
        if d not in self._listing:
            try:
                self._listing[d] = set(os.listdir(d))
            except OSError:
                self._listing[d] = set()
        return self._listing[d]

    def exists(self, rel_path):
        """Returns ('ok' | 'case' | 'missing', actual path on disk). 'case' = only upper/lowercase differs."""
        parts = [p for p in rel_path.split("/") if p not in ("", ".")]
        cur, case_issue, actual = self.root, False, []
        for p in parts:
            names = self.listdir(cur)
            if p in names:
                cur = os.path.join(cur, p); actual.append(p)
                continue
            match = next((n for n in names if n.lower() == p.lower()), None)
            if match is None:
                return "missing", None
            case_issue, cur = True, os.path.join(cur, match); actual.append(match)
        return ("case" if case_issue else "ok"), "/".join(actual)

    def ids_in(self, rel_path):
        if rel_path not in self._ids:
            try:
                text = open(os.path.join(self.root, rel_path), encoding="utf-8", errors="replace").read()
                self._ids[rel_path] = set(ID_ATTR.findall(text))
            except OSError:
                self._ids[rel_path] = set()
        return self._ids[rel_path]

    def files(self):
        for dp, dns, fns in os.walk(self.root):
            dns[:] = [d for d in dns if d not in self.skip]
            for fn in fns:
                if fn.lower().endswith(SCAN_EXTS):
                    path = os.path.join(dp, fn)
                    if self.include_unpublished or not self.unpublished(self.rel(path)):
                        yield path

    # ---------- link extraction
    def links(self, path, text):
        """Yields (link, offset, kind). Comments are ignored."""
        ext = os.path.splitext(path)[1].lower()
        if ext in (".html", ".htm", ".mjml", ".md", ".xml"):
            text = COMMENT["html"].sub(lambda m: " " * len(m.group(0)), text)
        if ext in (".css", ".js", ".mjs"):
            text = COMMENT["css"].sub(lambda m: " " * len(m.group(0)), text)
        if ext == ".md":  # examples inside ```code blocks``` and `inline code` aren't real links
            text = re.sub(r"```.*?```|`[^`\n]*`", lambda m: " " * len(m.group(0)), text, flags=re.S)

        if ext in (".html", ".htm", ".mjml", ".md", ".xml"):
            for m in ATTR_LINK.finditer(text):
                attr, value = m.group(1).lower(), m.group(3).strip()
                if attr == "content" and not re.match(r"https?://|/", value):
                    continue  # meta content is usually text, only check URLs
                if attr in ("srcset", "data-srcset"):
                    for part in value.split(","):
                        if part.strip():
                            yield part.strip().split()[0], m.start(3), "page"
                else:
                    yield value, m.start(3), "page"
            for m in CSS_URL.finditer(text):
                yield (m.group(2) or m.group(4)).strip(), m.start(), "page"
        if ext == ".md":
            for m in MD_LINK.finditer(text):
                yield m.group(1), m.start(1), "page"
        if ext == ".css":
            for m in CSS_URL.finditer(text):
                yield (m.group(2) or m.group(4)).strip(), m.start(), "page"
        if ext in (".js", ".mjs"):
            for m in JS_STRING.finditer(text):
                yield m.group(2), m.start(2), "js"
        if ext in (".json", ".webmanifest"):
            for m in JSON_LINK.finditer(text):
                yield m.group(1), m.start(1), "page"

    # ---------- resolution
    def resolve(self, src_rel, link):
        """Returns ('skip'|'external'|'local', target_rel_or_url, fragment)."""
        link = link.strip()
        if not link or link in IGNORE_EXACT or link.lower().startswith(IGNORE_PREFIXES) or re.search(r"\{\{|\{%|\$\{|<%", link):
            return "skip", None, None
        url, frag = urldefrag(link)
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https") or url.startswith("//"):
            host = parsed.netloc.lower().removeprefix("www.")
            if self.site and host == self.site:
                path = unquote(parsed.path)
            else:
                return "external", link, None
        elif parsed.scheme:
            return "skip", None, None
        else:
            path = unquote(parsed.path)
            if not path:  # just "#anchor" or "?query"
                return ("local", src_rel, frag) if frag else ("skip", None, None)
            if not path.startswith("/"):
                path = posixpath.join(posixpath.dirname("/" + src_rel), path)
        path = posixpath.normpath(path).lstrip("/")
        if path in ("", "."):
            path = "index.html"
        return "local", path, frag

    def check_local(self, src_rel, target, frag, kind, link=""):
        candidates = [target]
        if kind == "js" and not link.startswith(("/", "http")):
            # Paths in JS (fetch, image src, ...) resolve against the PAGE running the script,
            # not the .js file. Pages usually sit at the site root, so try that too.
            candidates.append(posixpath.normpath(urldefrag(unquote(link))[0].split("?")[0]).lstrip("/"))
        for cand in candidates:
            for variant in (cand, cand + ".html", posixpath.join(cand, "index.html")):
                state, actual = self.exists(variant)
                if state == "missing":
                    continue
                if state == "case":
                    return f"wrong upper/lowercase (works locally, breaks on the live site): file is {actual}"
                if self.unpublished(variant) and not self.unpublished(src_rel):
                    return "points into a folder the host won't publish (starts with _): " + variant
                if frag and variant.endswith((".html", ".htm")) and frag not in self.ids_in(variant):
                    return f"no element with id=\"{frag}\" in {variant}"
                return None
        if len(candidates) > 1:
            return f"missing file: tried {candidates[0]} (next to the script) and {candidates[1]} (site root)"
        return "missing file: " + target

    # ---------- main passes
    def scan(self):
        for path in self.files():
            src_rel = self.rel(path)
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            seen = set()
            for link, offset, kind in self.links(path, text):
                if (link, kind) in seen:
                    continue
                seen.add((link, kind))
                what, target, frag = self.resolve(src_rel, link)
                line = text.count("\n", 0, offset) + 1
                if what == "external":
                    self.external[target].add((src_rel, line))
                elif what == "local":
                    self.checked += 1
                    problem = self.check_local(src_rel, target, frag, kind, link)
                    if problem:
                        self.problems[src_rel].append((line, link, problem))

    def check_external(self, workers=12, timeout=20):
        def fetch(url):
            for method in ("HEAD", "GET"):
                try:
                    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
                    with urllib.request.urlopen(req, timeout=timeout) as r:
                        return url, r.status
                except urllib.error.HTTPError as e:
                    if method == "HEAD":
                        continue  # many servers reject HEAD; retry with GET
                    return url, e.code
                except Exception as e:
                    if method == "HEAD":
                        continue
                    return url, type(e).__name__
            return url, "error"

        self.broken_external, self.blocked_external = {}, {}
        with concurrent.futures.ThreadPoolExecutor(workers) as ex:
            for url, status in ex.map(fetch, sorted(self.external)):
                if isinstance(status, int) and 200 <= status < 400:
                    continue
                if status in (401, 403, 405, 429, 999):
                    self.blocked_external[url] = status
                elif status in (404, 410):
                    self.broken_external[url] = f"{status} page not found"
                elif status in ("TimeoutError", "timeout"):
                    self.broken_external[url] = "timed out"
                else:
                    self.broken_external[url] = f"could not load ({status})"

    def report(self, checked_external):
        local = sum(len(v) for v in self.problems.values())
        if self.problems:
            print("\n=== Local links ===")
        for src in sorted(self.problems):
            print(f"\n{src}")
            for line, link, problem in sorted(self.problems[src]):
                print(f"  line {line}: {link}\n      -> {problem}")

        def where(url):
            locs = sorted(self.external[url])
            shown = ", ".join(f"{s}:{l}" for s, l in locs[:4])
            return shown + (f" (+{len(locs) - 4} more)" if len(locs) > 4 else "")

        broken = getattr(self, "broken_external", {})
        blocked = getattr(self, "blocked_external", {})
        if broken:
            print("\n=== External links that failed ===")
            for url, why in sorted(broken.items()):
                print(f"  {url}\n      -> {why}\n      used in: {where(url)}")
        if blocked:
            print("\n=== External links the site refused to automated checks (open by hand) ===")
            for url, status in sorted(blocked.items()):
                print(f"  {url}  [{status}]\n      used in: {where(url)}")

        ext = f"{len(self.external)} external links " + ("checked" if checked_external else "not checked (use --external)")
        print(f"\nChecked {self.checked} local links and {ext}.")
        print(f"Problems: {local} local, {len(broken)} external failed, {len(blocked)} external to check by hand.")
        return local + len(broken)


def site_from_cname(root):
    try:
        return open(os.path.join(root, "CNAME"), encoding="utf-8").read().strip().lower().removeprefix("www.")
    except OSError:
        return None


def main():
    here = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    p = argparse.ArgumentParser(description="Report broken links in a static site. Never changes files.")
    p.add_argument("root", nargs="?", default=here, help="project folder (default: the folder above utils/)")
    p.add_argument("--site", help="the site's domain, e.g. example.org (default: read from CNAME)")
    p.add_argument("--external", action="store_true", help="also check links to other websites (slower)")
    p.add_argument("--skip", action="append", default=[], help="folder name to skip (repeatable)")
    p.add_argument("--include-unpublished", action="store_true",
                   help="also scan files in '_' folders that GitHub Pages doesn't publish")
    args = p.parse_args()

    site = (args.site or site_from_cname(args.root) or "").lower().removeprefix("https://").removeprefix("http://")
    site = site.strip("/").removeprefix("www.") or None
    checker = Checker(args.root, site, args.skip, args.include_unpublished)
    print(f"Checking {checker.root}" + (f" (site: {site})" if site else ""))
    checker.scan()
    if args.external:
        checker.check_external()
    sys.exit(1 if checker.report(args.external) else 0)


if __name__ == "__main__":
    main()
