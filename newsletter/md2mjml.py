from pathlib import Path
import re
import html
import subprocess
import shutil


NEWSLETTERS_DIR = Path("newsletter")
TEMPLATE_FILE = NEWSLETTERS_DIR / "template.mjml"

BASE_HTML_URL = "https://raleighcommunitykickstand.org/newsletter/"
BASE_IMAGE_URL = "https://raleighcommunitykickstand.org/newsletter/images/"
LOCAL_IMAGE_DIR = NEWSLETTERS_DIR / "images"

IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif"]


def escape_text(text: str) -> str:
    return html.escape(text, quote=True)


def inline_markdown_to_html(text: str) -> str:
    text = escape_text(text)
    text = re.sub(r"\\([^\w\s])", r"\1", text)
    text = re.sub(
        r"(?<!!)\[(.+?)\]\((.+?)\)",
        r'<a href="\2" style="color:#148378; text-decoration:underline;">\1</a>',
        text,
    )
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

    if not sections:
        raise ValueError("Expected at least one '##' section")

    return newsletter_title, sections


def find_image_filename(image_stem: str) -> str:
    if not image_stem:
        return ""

    for ext in IMAGE_EXTENSIONS:
        filename = f"{image_stem}{ext}"
        local_path = LOCAL_IMAGE_DIR / filename
        if local_path.exists():
            return filename

    return ""


def image_tag_from_filename(filename: str, alt: str) -> str:
    return f"""
        <mj-image
          src="{BASE_IMAGE_URL}{filename}"
          alt="{escape_text(alt)}"
          width="400px"
          fluid-on-mobile="true"
          align="center"
          padding="0 0 16px 0"
        />
        """.strip()


def image_tag_or_empty(image_stem: str, alt: str) -> str:
    filename = find_image_filename(image_stem)
    if not filename:
        return ""
    return image_tag_from_filename(filename, alt)


def markdown_image_to_mjml(block: str) -> str:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if len(lines) != 1:
        return ""

    m = re.fullmatch(r"!\[(.*?)\]\((images/[^)]+)\)", lines[0])
    if not m:
        return ""

    alt_text = m.group(1).strip()
    rel_path = m.group(2).strip()

    filename = Path(rel_path).name
    local_path = LOCAL_IMAGE_DIR / filename

    if not local_path.exists():
        return ""

    return image_tag_from_filename(filename, alt_text or filename)


def section_body_to_mjml(body: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
    rendered = []

    image_line_re = re.compile(r"!\[(.*?)\]\((images/[^)]+)\)")

    for i, block in enumerate(blocks):
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]

        # special case: first block starts with "Flyer by"
        if i == 0 and lines and lines[0].lower().startswith("flyer by"):
            content = "<br />\n          ".join(inline_markdown_to_html(line) for line in lines)
            rendered.append(
                f"""<mj-text
          align="center"
          font-size="13px"
          color="#dae0e5"
          padding-bottom="12px"
        >
          {content}
        </mj-text>"""
            )
            continue

        text_buffer = []

        def flush_text_buffer():
            nonlocal text_buffer
            if not text_buffer:
                return
            content = "<br />\n          ".join(inline_markdown_to_html(line) for line in text_buffer)
            rendered.append(
                f"""<mj-text padding-bottom="16px" align="left">
          {content}
        </mj-text>"""
            )
            text_buffer = []

        for line in lines:
            m = image_line_re.fullmatch(line.strip())

            if m:
                # flush any text collected before the image
                flush_text_buffer()

                alt_text = m.group(1).strip()
                rel_path = m.group(2).strip()
                filename = Path(rel_path).name
                local_path = LOCAL_IMAGE_DIR / filename

                if local_path.exists():
                    rendered.append(image_tag_from_filename(filename, alt_text or filename))
                else:
                    # if missing, just keep original markdown visible
                    rendered.append(
                        f"""<mj-text padding-bottom="16px" align="left">
          {inline_markdown_to_html(line)}
        </mj-text>"""
                    )
            else:
                text_buffer.append(line)

        # flush trailing text after any image lines
        flush_text_buffer()

    return "\n        ".join(rendered)


def render_section(title: str, body: str) -> str:

    return f"""
    <mj-section>
      <mj-column>
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
    markdown = markdown_file.read_text(encoding="utf-8")

    newsletter_title, sections = parse_markdown(markdown)

    rendered_sections = []
    for section_title, section_body in sections:
        # image_stem = image_stem_for_section(month_slug, section_title)
        rendered_sections.append(
            # render_section(section_title, section_body, image_stem)
            render_section(section_title, section_body)
        )

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
    slugs = sorted(slugs)

    js_content = "const newsletters = [\n"
    for slug in slugs:
        js_content += f'  "{slug}",\n'
    js_content += "];\n"

    js_path.write_text(js_content, encoding="utf-8")
    print(f"Wrote {js_path}")


def main():
    md_files = sorted(
        p for p in NEWSLETTERS_DIR.glob("*.md")
        if p.name.lower() != "template.md"
    )

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