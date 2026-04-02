from pathlib import Path
import re
import html

TEMPLATE_FILE = Path("newsletter/template.mjml")
MARKDOWN_FILE = Path("newsletter/2026_04.md")
OUTPUT_FILE = Path("newsletter/2026_04.mjml")

BASE_IMAGE_URL = "https://raleighcommunitykickstand.org/newsletter/images/"
LOCAL_IMAGE_DIR = Path("newsletter/images")
SECTION_1_IMAGE = "2026_04_wrapup.png"
SECTION_2_IMAGE = "2026_04_flyer.png"

def escape_text(text: str) -> str:
    return html.escape(text, quote=True)


def inline_markdown_to_html(text: str) -> str:
    text = escape_text(text)
    text = re.sub(r"\\([!#\-\\()])", r"\1", text)
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return text


def parse_markdown(md: str):
    title_match = re.search(r"^#\s+(.+)$", md, flags=re.MULTILINE)
    if not title_match:
        raise ValueError("Missing top-level '# Newsletter Title'")

    newsletter_title = title_match.group(1).strip().upper()

    parts = re.split(r"^##\s+(.+?)\s*$", md, flags=re.MULTILINE)
    sections = []
    for i in range(1, len(parts), 2):
        sec_title = parts[i].strip()
        sec_body = parts[i + 1].strip()
        sections.append((sec_title, sec_body))

    if len(sections) < 2:
        raise ValueError("Expected at least two '##' sections")

    return newsletter_title, sections[0], sections[1]

def image_tag_or_empty(filename: str, alt: str) -> str:
    local_path = LOCAL_IMAGE_DIR / filename

    if local_path.exists():
        return f"""
        <mj-image
          src="{BASE_IMAGE_URL}{filename}"
          alt="{alt}"
          width="220px"
          align="center"
          padding="0 0 16px 0"
        />
        """.strip()
    else:
        return ""

def section_body_to_mjml(body: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
    rendered = []

    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines()]

        # preserve intentional line breaks when block has multiple lines
        if len(lines) > 1:
            content = "<br />\n          ".join(inline_markdown_to_html(line) for line in lines)
        else:
            content = inline_markdown_to_html(lines[0])

        rendered.append(
            f"""<mj-text padding-bottom="16px" align="left">
          {content}
        </mj-text>"""
        )

    return "\n        ".join(rendered)


def main():
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    markdown = MARKDOWN_FILE.read_text(encoding="utf-8")

    newsletter_title, (section1_title, section1_body), (section2_title, section2_body) = parse_markdown(markdown)

    result = template
    result = result.replace("{{ NEWSLETTER_TITLE }}", escape_text(newsletter_title))
    result = result.replace("{{ SECTION_1_TITLE }}", escape_text(section1_title.upper()))
    result = result.replace("{{ SECTION_1_IMAGE }}", image_tag_or_empty(SECTION_1_IMAGE, "Monthly Summary"))
    result = result.replace("{{ SECTION_1_BODY }}", section_body_to_mjml(section1_body))
    result = result.replace("{{ SECTION_2_TITLE }}", escape_text(section2_title.upper()))
    result = result.replace("{{ SECTION_2_IMAGE }}", image_tag_or_empty(SECTION_2_IMAGE, "Event Flyer"))
    result = result.replace("{{ SECTION_2_BODY }}", section_body_to_mjml(section2_body))

    OUTPUT_FILE.write_text(result, encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()