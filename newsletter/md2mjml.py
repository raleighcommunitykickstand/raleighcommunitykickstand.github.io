from pathlib import Path
import html
import re
import shutil
import subprocess
from ftfy import fix_text


from bs4 import BeautifulSoup, NavigableString, Tag


NEWSLETTERS_DIR = Path("newsletter")
TEMPLATE_FILE = NEWSLETTERS_DIR / "template.mjml"
LOCAL_IMAGE_DIR = NEWSLETTERS_DIR / "images"
MARKED_RENDERER = NEWSLETTERS_DIR / "render_markdown.mjs"

BASE_HTML_URL = "https://raleighcommunitykickstand.org/newsletter/"
BASE_IMAGE_URL = "https://raleighcommunitykickstand.org/newsletter/images/"

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".webp"]

HEADING_SIZES = {
    "h1": "28px",
    "h2": "24px",
    "h3": "20px",
    "h4": "18px",
    "h5": "16px",
    "h6": "15px",
}


def read_markdown_file(path: Path) -> str:
    for encoding in ("utf-8", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError(f"Could not decode {path}")

def clean_markdown_text(path: Path) -> str:
    text = read_markdown_file(path)
    return fix_text(text)

def escape_text(text: str) -> str:
    return html.escape(text, quote=True)

def paragraph_is_caption_only(text: str) -> bool:
    t = text.strip().lower()
    return t.startswith("flyer by") or t.startswith("photo by")

def parse_markdown(md: str) -> tuple[str, list[tuple[str, str]]]:
    title_match = re.search(r"^#\s+(.+)$", md, flags=re.MULTILINE)
    if not title_match:
        raise ValueError("Missing top-level '# Newsletter Title'")

    newsletter_title = title_match.group(1).strip().upper()

    parts = re.split(r"^##\s+(.+?)\s*$", md, flags=re.MULTILINE)
    sections = []

    for i in range(1, len(parts), 2):
        section_title = parts[i].strip()
        section_body = parts[i + 1].strip()
        sections.append((section_title, section_body))

    if not sections:
        raise ValueError("Expected at least one '##' section")

    return newsletter_title, sections


def markdown_to_html_with_marked(md: str) -> str:
    node_exe = shutil.which("node")
    if not node_exe:
        raise FileNotFoundError("Could not find node on PATH")

    if not MARKED_RENDERER.exists():
        raise FileNotFoundError(f"Missing Marked helper: {MARKED_RENDERER}")

    result = subprocess.run(
        [node_exe, str(MARKED_RENDERER)],
        input=md,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


def resolve_and_validate_image(src: str) -> tuple[str, str]:
    """
    Returns (production_url, filename).
    """
    src = (src or "").strip()
    if not src:
        raise ValueError("Empty image src")

    if re.match(r"^https?://", src, flags=re.IGNORECASE):
        return src, Path(src).name

    filename = Path(src).name
    local_path = LOCAL_IMAGE_DIR / filename

    if not local_path.exists():
        raise FileNotFoundError(
            f"Image not found: {filename}\n"
            f"Expected at: {local_path}\n"
            f"Original src: {src}"
        )

    return BASE_IMAGE_URL + filename, filename


def paragraph_is_only_image(node: Tag) -> Tag | None:
    meaningful_children = []

    for child in node.contents:
        if isinstance(child, NavigableString):
            if child.strip():
                meaningful_children.append(child)
        elif isinstance(child, Tag):
            meaningful_children.append(child)

    if (
        len(meaningful_children) == 1
        and isinstance(meaningful_children[0], Tag)
        and meaningful_children[0].name.lower() == "img"
    ):
        return meaningful_children[0]

    return None


def paragraph_is_caption_only(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered.startswith("flyer by") or lowered.startswith("photo by")


def mj_text_block(content: str, align: str = "left", extra_attrs: str = "") -> str:
    attrs = f' color="#ffffff" align="{align}"'
    if extra_attrs:
        attrs += f" {extra_attrs.strip()}"

    return f"""<mj-text{attrs}>
          {content}
        </mj-text>"""


def mj_image_block(src: str, alt: str) -> str:
    return f"""
        <mj-image
          src="{escape_text(src)}"
          alt="{escape_text(alt)}"
          width="400px"
          fluid-on-mobile="true"
          align="center"
          padding="0 0 16px 0"
        />
        """.strip()


def render_inline_html(node) -> str:
    if isinstance(node, NavigableString):
        return escape_text(str(node))

    if not isinstance(node, Tag):
        return ""

    name = node.name.lower()
    inner = "".join(render_inline_html(child) for child in node.children)

    if name in {"strong", "b"}:
        return f"<strong>{inner}</strong>"

    if name in {"em", "i"}:
        return f"<em>{inner}</em>"

    if name == "code":
        return (
            "<code style=\""
            "background:#111;"
            "color:#f5f5f5;"
            "padding:2px 4px;"
            "border-radius:3px;"
            "font-family:Courier New, Courier, monospace;"
            "\">"
            f"{inner}"
            "</code>"
        )

    if name == "a":
        href = escape_text(node.get("href", ""))
        return f'<a href="{href}" style="color:#148378; text-decoration:underline;">{inner}</a>'

    if name == "br":
        return "<br />"

    if name == "span":
        return inner

    return inner


def render_paragraph_block(node: Tag) -> str:
    image = paragraph_is_only_image(node)
    if image is not None:
        src, filename = resolve_and_validate_image(image.get("src", ""))
        alt = image.get("alt", "") or filename
        return mj_image_block(src, alt)

    content = "".join(render_inline_html(child) for child in node.children).strip()
    if not content:
        return ""

    if paragraph_is_caption_only(content):
        return mj_text_block(
            content,
            align="center",
            extra_attrs='font-size="13px" color="#dae0e5" padding-bottom="12px"',
        )

    return mj_text_block(content)


def render_pre_block(node: Tag) -> str:
    code_text = node.get_text()
    content = (
        '<pre style="'
        'margin:0; '
        'white-space:pre-wrap; '
        'background:#111; '
        'color:#f5f5f5; '
        'padding:12px; '
        'border-radius:4px; '
        'font-family:Courier New, Courier, monospace; '
        'font-size:14px; '
        'line-height:1.5;'
        '">'
        f"{escape_text(code_text)}"
        "</pre>"
    )
    return mj_text_block(content)


def render_list_block(node: Tag) -> str:
    tag_name = node.name.lower()
    items = []

    for li in node.find_all("li", recursive=False):
        li_html = "".join(render_inline_html(child) for child in li.children).strip()
        items.append(f"<li>{li_html}</li>")

    return mj_text_block(f"<{tag_name}>{''.join(items)}</{tag_name}>")


def render_blockquote_block(node: Tag) -> str:
    content = "".join(render_inline_html(child) for child in node.children).strip()
    block = (
        '<div style="'
        'border-left:4px solid #148378; '
        'padding-left:12px; '
        'color:#dae0e5;'
        '">'
        f"{content}"
        "</div>"
    )
    return mj_text_block(block)


def render_heading_block(node: Tag) -> str:
    name = node.name.lower()
    content = "".join(render_inline_html(child) for child in node.children).strip()

    return mj_text_block(
        content,
        extra_attrs=(
            f'font-size="{HEADING_SIZES[name]}" '
            'font-weight="700" '
            'line-height="1.2" '
            'padding-bottom="10px"'
        ),
    )


def render_image_block(node: Tag) -> str:
    src, filename = resolve_and_validate_image(node.get("src", ""))
    alt = node.get("alt", "") or filename
    return mj_image_block(src, alt)


def html_block_to_mjml(node: Tag) -> str:
    name = node.name.lower()

    if name == "p":
        return render_paragraph_block(node)

    if name == "pre":
        return render_pre_block(node)

    if name in {"ul", "ol"}:
        return render_list_block(node)

    if name == "blockquote":
        return render_blockquote_block(node)

    if name == "hr":
        return """
        <mj-divider
          border-width="1px"
          border-style="solid"
          border-color="#148378"
          padding="8px 0 24px 0"
        />
        """.strip()

    if name == "img":
        return render_image_block(node)

    if name == "table":
        return mj_text_block(str(node))

    if name in HEADING_SIZES:
        return render_heading_block(node)

    return mj_text_block(str(node))


def section_body_to_mjml(body: str) -> str:
    html_body = markdown_to_html_with_marked(body)
    soup = BeautifulSoup(html_body, "html.parser")
    rendered_blocks = []

    for node in soup.contents:
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                rendered_blocks.append(mj_text_block(escape_text(text)))
            continue

        if isinstance(node, Tag):
            block = html_block_to_mjml(node)
            if block:
                rendered_blocks.append(block)

    return "\n        ".join(rendered_blocks)


def render_section(title: str, body: str) -> str:
    return f"""
    <mj-section>
      <mj-column background-color="#1d2124" border="2px solid #f7f573">
        <mj-text
          font-family="'Courier New', Courier, monospace"
          color="#148378"
          font-size="32px"
          line-height="1.05"
          font-weight="700"
          align="center"
          padding-bottom="14px"
        >
          {escape_text(title.upper())}
        </mj-text>
        {section_body_to_mjml(body)}
      </mj-column>
    </mj-section>
    """.strip()


def compile_mjml_to_html(mjml_path: Path):
    html_path = mjml_path.with_suffix(".html")
    npx_exe = shutil.which("npx.cmd") or shutil.which("npx")

    if not npx_exe:
        raise FileNotFoundError("Could not find npx or npx.cmd on PATH")

    subprocess.run(
        [npx_exe, "mjml", str(mjml_path), "-o", str(html_path)],
        check=True,
    )
    print(f"Compiled {html_path}")


def create_mjml(month_slug: str) -> Path:
    markdown_file = NEWSLETTERS_DIR / f"{month_slug}.md"
    output_file = NEWSLETTERS_DIR / f"{month_slug}.mjml"
    html_link = f"{BASE_HTML_URL}{month_slug}.html"

    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    markdown = clean_markdown_text(markdown_file)

    newsletter_title, sections = parse_markdown(markdown)

    rendered_sections = [
        render_section(section_title, section_body)
        for section_title, section_body in sections
    ]
    content_sections = "\n\n".join(rendered_sections)

    result = template
    result = result.replace("{{ NEWSLETTER_TITLE }}", escape_text(newsletter_title))
    result = result.replace("{{ VIEW_IN_BROWSER }}", html_link)
    result = result.replace("{{ CONTENT_SECTIONS }}", content_sections)

    output_file.write_text(result, encoding="utf-8")
    print(f"Wrote {output_file}")

    compile_mjml_to_html(output_file)
    return output_file


def write_newsletters_js(slugs: list[str]):
    js_path = NEWSLETTERS_DIR / "newsletters.js"
    sorted_slugs = sorted(slugs)

    js_content = "const newsletters = [\n"
    for slug in sorted_slugs:
        js_content += f'  "{slug}",\n'
    js_content += "];\n"

    js_path.write_text(js_content, encoding="utf-8")
    print(f"Wrote {js_path}")


def iter_newsletter_markdown_files():
    return sorted(
        path
        for path in NEWSLETTERS_DIR.glob("*.md")
        if path.name.lower() != "template.md"
    )


def main():
    md_files = iter_newsletter_markdown_files()

    if not md_files:
        print(f"No markdown files found in {NEWSLETTERS_DIR}")
        return

    slugs = []

    for md_file in md_files:
        month_slug = md_file.stem

        if not re.fullmatch(r"\d{4}_\d{2}", month_slug):
            print(f"Skipping {md_file.name} (expected format YYYY_MM.md)")
            continue

        slugs.append(month_slug)

        try:
            create_mjml(month_slug)
        except Exception as e:
            print(f"Failed for {md_file.name}: {e}")

    write_newsletters_js(slugs)


if __name__ == "__main__":
    main()