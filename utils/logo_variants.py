"""
Make color variants of every logo in _media/logos/ as SVG + PNG, in media/logos/ (published).

Each logo is drawn in dark "ink" (the shapes) plus light "inner" parts (the text and
negative space inside the shapes). Each ink color gets the inner colors listed for it
(INNERS_FOR_INK, else DEFAULT_INNERS):

    logo-rck-circle-teal-white.svg    teal shapes, white text/inner space
    logo-rck-circle-teal-black.svg    teal shapes, black text/inner space
    logo-rck-circle-teal-clear.svg    teal shapes, see-through text/inner space
    logo-rck-circle-black-yellow.svg  black shapes, yellow text/inner space
    logo-rck-plain-teal.svg           logos with no inner parts get one file per ink color

Sources, per logo name (an .svg wins over an .ai of the same name):
  - <name>.svg  exported from Illustrator (black/white artwork)
  - <name>.ai   saved with "Create PDF Compatible File" (Illustrator's default); live text
                is converted to outlines using the font embedded in the file

PNGs are rendered with ImageMagick (`magick`).

    python utils/logo_variants.py              # all logos
    python utils/logo_variants.py logo-rck     # only logos whose name starts with this
"""

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zlib

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "_media", "logos")
OUT_DIR = os.path.join(ROOT_DIR, "media", "logos")  # published: the site and emails can use these

INKS = {
    "yellow": "#f7f573",
    "teal": "#148378",
    "blue": "#17a2b8",
    "orange": "#ef4036",
    "black": "#000000",
}
INNERS = {
    "white": "#ffffff",
    "black": "#000000",
    "yellow": "#f7f573",
    "clear": None,  # transparent
}
# Which inner colors each ink color gets
DEFAULT_INNERS = ["white", "black", "clear"]
INNERS_FOR_INK = {
    "black": ["yellow", "clear", "white"],
}
PNG_WIDTH = 1200

# logo-* files get every color variant. badge-* files ($ amounts, fix/teach/give) get one
# version only: black with white text/inner space, saved as badge-<name>.svg/.png.
# Anything else in _media/logos/ (e.g. handlebars) is skipped.
LOGO_PREFIX = "logo-"
BADGE_PREFIX = "badge-"


# ---------------------------------------------------------------- PDF (.ai) reading

TOKEN = re.compile(
    rb"\s*(?:"
    rb"(?P<dopen><<)|(?P<dclose>>>)|(?P<aopen>\[)|(?P<aclose>\])"
    rb"|(?P<name>/[^\s/\[\]()<>{}%]*)"
    rb"|(?P<num>[-+]?(?:\d+\.?\d*|\.\d+))"
    rb"|(?P<str>\()|(?P<hex><[0-9A-Fa-f\s]*>)"
    rb"|(?P<word>[A-Za-z*'\"][A-Za-z0-9*'\"]*)"
    rb"|(?P<comment>%[^\r\n]*)"
    rb")"
)


class Ref:
    def __init__(self, num):
        self.num = num


def read_string(data, pos):
    """Read a (literal) string starting just after '('. Returns (bytes, new_pos)."""
    out, depth, i = bytearray(), 1, pos
    escapes = {b"n": 10, b"r": 13, b"t": 9, b"b": 8, b"f": 12}
    while i < len(data):
        ch = data[i : i + 1]
        if ch == b"\\":
            nxt = data[i + 1 : i + 2]
            if nxt in escapes:
                out.append(escapes[nxt])
                i += 2
            elif nxt.isdigit():
                m = re.match(rb"[0-7]{1,3}", data[i + 1 : i + 4])
                out.append(int(m.group(0), 8) & 255)
                i += 1 + len(m.group(0))
            elif nxt in (b"\r", b"\n"):
                i += 2
            else:
                out += nxt
                i += 2
            continue
        if ch == b"(":
            depth += 1
        elif ch == b")":
            depth -= 1
            if depth == 0:
                return bytes(out), i + 1
        out += ch
        i += 1
    return bytes(out), i


def tokens(data, pos=0):
    """Yield PDF tokens: numbers, names ('/x'), bytes strings, ('word', w), dict/array markers."""
    while pos < len(data):
        m = TOKEN.match(data, pos)
        if not m or m.end() == pos:
            pos += 1
            continue
        pos = m.end()
        kind = m.lastgroup
        if kind == "comment":
            continue
        if kind == "str":
            s, pos = read_string(data, pos)
            yield ("str", s), pos
        elif kind == "hex":
            h = re.sub(rb"\s", b"", m.group("hex")[1:-1])
            yield ("str", bytes.fromhex((h + b"0" * (len(h) % 2)).decode())), pos
        elif kind == "num":
            yield ("num", float(m.group("num"))), pos
        elif kind == "name":
            yield ("name", m.group("name")[1:].decode("latin1")), pos
        elif kind == "word":
            yield ("word", m.group("word").decode("latin1")), pos
        else:
            yield (kind, None), pos


def parse_value(it):
    """Parse one PDF value from a token iterator (handles dicts, arrays and 'n 0 R' refs)."""
    (kind, val), _ = next(it)
    if kind == "dopen":
        d = {}
        while True:
            (k, key), _ = next(it)
            if k == "dclose":
                return d
            d[key] = parse_value(it)
    if kind == "aopen":
        arr = []
        while True:
            peek = next(it)
            if peek[0][0] == "aclose":
                return arr
            arr.append(parse_value(_chain(peek, it)))
            # collapse "n 0 R" into a Ref
            if len(arr) >= 3 and arr[-1] == "R" and isinstance(arr[-3], float):
                arr[-3:] = [Ref(int(arr[-3]))]
    if kind == "num":
        return val
    if kind == "word":
        return val
    return val


def _chain(first, it):
    yield first
    yield from it


def parse_dict_at(data, pos):
    """Parse the dict starting at data[pos] ('<<'), resolving 'n 0 R' refs inside it."""
    it = tokens(data, pos)
    stack, result = [], None
    pending = []
    for (kind, val), _ in it:
        if kind in ("dopen", "aopen"):
            stack.append(({} if kind == "dopen" else [], []))
            continue
        if kind in ("dclose", "aclose"):
            container, items = stack.pop()
            items = _collapse_refs(items)
            if isinstance(container, dict):
                for i in range(0, len(items) - 1, 2):
                    container[items[i]] = items[i + 1]
            else:
                container.extend(items)
            if not stack:
                return container
            stack[-1][1].append(container)
            continue
        if stack:
            stack[-1][1].append(val)
    return result


def _collapse_refs(items):
    out = []
    for item in items:
        out.append(item)
        if len(out) >= 3 and out[-1] == "R" and isinstance(out[-2], float) and isinstance(out[-3], float):
            num = int(out[-3])
            out[-3:] = [Ref(num)]
    return out


class PdfFile:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        self.offsets = {}
        for m in re.finditer(rb"(?<![\d])(\d+)\s+0\s+obj\b", self.data):
            self.offsets[int(m.group(1))] = m.end()  # last definition wins (incremental saves)

    def obj(self, num):
        """Returns (dict_or_value, stream_bytes_or_None)."""
        pos = self.offsets[num]
        start = self.data.index(b"<<", pos) if self.data[pos:pos + 20].lstrip().startswith(b"<<") else None
        if start is None:
            it = tokens(self.data, pos)
            return parse_value(it), None
        d = parse_dict_at(self.data, start)
        m = re.compile(rb">>\s*stream\r?\n").search(self.data, start)
        endobj = self.data.find(b"endobj", start)
        if m and m.start() < endobj:
            s0 = m.end()
            length = d.get("Length")
            if isinstance(length, Ref):
                length = self.obj(length.num)[0]
            raw = self.data[s0 : s0 + int(length)] if isinstance(length, float) else self.data[s0 : self.data.find(b"endstream", s0)]
            if "FlateDecode" in str(d.get("Filter", "")):
                raw = zlib.decompress(raw)
            return d, raw
        return d, None

    def resolve(self, v):
        return self.obj(v.num)[0] if isinstance(v, Ref) else v

    def first_page(self):
        for num in sorted(self.offsets):
            pos = self.offsets[num]
            head = self.data[pos : pos + 400]
            if re.search(rb"/Type\s*/Page(?![s\w])", head):
                d, _ = self.obj(num)
                if d.get("Type") == "Page":
                    return d
        raise ValueError("no page found")


def mat_mul(a, b):
    """PDF matrices [a b c d e f]; returns a x b (apply a, then b)."""
    return [
        a[0] * b[0] + a[1] * b[2],
        a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2],
        a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4],
        a[4] * b[1] + a[5] * b[3] + b[5],
    ]


def apply(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def color_from(comps):
    comps = [float(c) for c in comps]
    if len(comps) == 1:
        g = comps[0]
        return (g, g, g)
    if len(comps) == 3:
        return tuple(comps)
    if len(comps) == 4:
        c, m, y, k = comps
        return ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
    return (0, 0, 0)


def to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v * 255))) for v in rgb)


class Font:
    def __init__(self, pdf, font_dict):
        self.first = int(font_dict.get("FirstChar", 0))
        self.widths = [float(w) for w in pdf.resolve(font_dict.get("Widths", []))]
        desc = pdf.resolve(font_dict.get("FontDescriptor"))
        ref = desc.get("FontFile2") if desc else None
        if not ref:
            raise ValueError(f"font {font_dict.get('BaseFont')} has no embedded TrueType outlines")
        self.tt = TTFont(io.BytesIO(pdf.obj(ref.num)[1]))
        self.upm = self.tt["head"].unitsPerEm
        self.glyphs = self.tt.getGlyphSet()
        self.cmaps = {(t.platformID, t.platEncID): t.cmap for t in self.tt["cmap"].tables}

    def glyph_name(self, code):
        for key, lookup in (((3, 0), 0xF000 + code), ((1, 0), code), ((3, 1), ord(bytes([code]).decode("cp1252", "replace")))):
            name = self.cmaps.get(key, {}).get(lookup)
            if name:
                return name
        return None

    def width(self, code):
        i = code - self.first
        return self.widths[i] / 1000 if 0 <= i < len(self.widths) else 0.5


def ai_to_svg(path):
    """Convert a PDF-compatible .ai file's artwork to SVG text with explicit fills."""
    pdf = PdfFile(path)
    page = pdf.first_page()
    box = page.get("ArtBox") or page.get("CropBox") or page.get("MediaBox")
    x0, y0, x1, y1 = [float(v) for v in pdf.resolve(box)]
    res = pdf.resolve(page.get("Resources", {}))
    fonts = {k: pdf.resolve(v) for k, v in pdf.resolve(res.get("Font", {})).items()}
    if pdf.resolve(res.get("XObject", {})):
        raise ValueError("saved without PDF content; re-save with 'Create PDF Compatible File' or export an SVG")

    contents = page.get("Contents")
    refs = contents if isinstance(contents, list) else [contents]
    stream = b"\n".join(pdf.obj(r.num)[1] for r in refs)

    loaded_fonts = {}
    shapes = []  # (svg path d, fill hex or None, stroke hex or None, stroke width, evenodd)

    def pt(m, x, y):
        X, Y = apply(m, x, y)
        return f"{X - x0:.2f} {y1 - Y:.2f}"

    gs = {"ctm": [1, 0, 0, 1, 0, 0], "fill": (0, 0, 0), "stroke": (0, 0, 0), "lw": 1.0}
    stack, operands, path, cur = [], [], [], (0, 0)
    text = {"tm": None, "tlm": None, "font": None, "size": 1, "tc": 0, "tw": 0, "th": 1, "tl": 0, "rise": 0}

    def emit(fill, stroke, evenodd=False):
        if path:
            scale = (abs(gs["ctm"][0] * gs["ctm"][3] - gs["ctm"][1] * gs["ctm"][2])) ** 0.5
            shapes.append((" ".join(path), to_hex(gs["fill"]) if fill else None, to_hex(gs["stroke"]) if stroke else None, gs["lw"] * scale, evenodd))

    def show(s):
        font = text["font"]
        if font is None:
            return
        for code in s:
            trm = mat_mul(mat_mul([text["size"] * text["th"], 0, 0, text["size"], 0, text["rise"]], text["tm"]), gs["ctm"])
            name = font.glyph_name(code)
            if name and name in font.glyphs:
                pen = SVGPathPen(font.glyphs)
                k = 1 / font.upm
                m = mat_mul([k, 0, 0, k, 0, 0], trm)
                flip = mat_mul(m, [1, 0, 0, -1, -x0, y1])
                font.glyphs[name].draw(TransformPen(pen, tuple(flip)))
                d = pen.getCommands()
                if d:
                    shapes.append((d, to_hex(gs["fill"]), None, 0, False))
            adv = (font.width(code) * text["size"] + text["tc"] + (text["tw"] if code == 32 else 0)) * text["th"]
            text["tm"] = mat_mul([1, 0, 0, 1, adv, 0], text["tm"])

    it = tokens(stream)
    for (kind, val), _ in it:
        if kind == "aopen":  # TJ array
            arr = []
            for (k2, v2), _ in it:
                if k2 == "aclose":
                    break
                arr.append(v2)
            operands.append(arr)
            continue
        if kind == "dopen":  # inline dict (BDC properties): skip
            depth = 1
            for (k2, _v), _ in it:
                depth += k2 == "dopen"
                depth -= k2 == "dclose"
                if depth == 0:
                    break
            operands.append({})
            continue
        if kind != "word":
            operands.append(val)
            continue

        op, o = val, operands
        ctm = gs["ctm"]
        if op == "q":
            stack.append(dict(gs))
        elif op == "Q":
            gs = stack.pop() if stack else gs
        elif op == "cm":
            gs["ctm"] = mat_mul([float(v) for v in o[-6:]], ctm)
        elif op == "w":
            gs["lw"] = float(o[-1])
        elif op in ("g", "rg", "k", "sc", "scn"):
            gs["fill"] = color_from([v for v in o if isinstance(v, float)])
        elif op in ("G", "RG", "K", "SC", "SCN"):
            gs["stroke"] = color_from([v for v in o if isinstance(v, float)])
        elif op == "m":
            cur = (o[-2], o[-1])
            path.append("M " + pt(ctm, *cur))
        elif op == "l":
            cur = (o[-2], o[-1])
            path.append("L " + pt(ctm, *cur))
        elif op == "c":
            a = o[-6:]
            path.append("C " + " ".join(pt(ctm, a[i], a[i + 1]) for i in (0, 2, 4)))
            cur = (a[4], a[5])
        elif op == "v":
            a = o[-4:]
            path.append("C " + " ".join([pt(ctm, *cur), pt(ctm, a[0], a[1]), pt(ctm, a[2], a[3])]))
            cur = (a[2], a[3])
        elif op == "y":
            a = o[-4:]
            path.append("C " + " ".join([pt(ctm, a[0], a[1]), pt(ctm, a[2], a[3]), pt(ctm, a[2], a[3])]))
            cur = (a[2], a[3])
        elif op == "h":
            path.append("Z")
        elif op == "re":
            x, y, w, h = o[-4:]
            path.append(f"M {pt(ctm, x, y)} L {pt(ctm, x + w, y)} L {pt(ctm, x + w, y + h)} L {pt(ctm, x, y + h)} Z")
        elif op in ("f", "F", "f*"):
            emit(True, False, op == "f*")
            path = []
        elif op in ("S", "s"):
            if op == "s":
                path.append("Z")
            emit(False, True)
            path = []
        elif op in ("B", "B*", "b", "b*"):
            if op.startswith("b"):
                path.append("Z")
            emit(True, True, op.endswith("*"))
            path = []
        elif op == "n":
            path = []  # end of a clipping path; clipping is ignored
        elif op == "BT":
            text["tm"] = text["tlm"] = [1, 0, 0, 1, 0, 0]
        elif op == "Tf":
            name = o[-2]
            if name not in loaded_fonts:
                loaded_fonts[name] = Font(pdf, fonts[name])
            text["font"], text["size"] = loaded_fonts[name], float(o[-1])
        elif op == "Tc":
            text["tc"] = float(o[-1])
        elif op == "Tw":
            text["tw"] = float(o[-1])
        elif op == "Tz":
            text["th"] = float(o[-1]) / 100
        elif op == "TL":
            text["tl"] = float(o[-1])
        elif op == "Ts":
            text["rise"] = float(o[-1])
        elif op == "Tm":
            text["tm"] = text["tlm"] = [float(v) for v in o[-6:]]
        elif op in ("Td", "TD"):
            tx, ty = float(o[-2]), float(o[-1])
            if op == "TD":
                text["tl"] = -ty
            text["tm"] = text["tlm"] = mat_mul([1, 0, 0, 1, tx, ty], text["tlm"])
        elif op == "T*":
            text["tm"] = text["tlm"] = mat_mul([1, 0, 0, 1, 0, -text["tl"]], text["tlm"])
        elif op == "Tj":
            show(o[-1])
        elif op == "TJ":
            for item in o[-1]:
                if isinstance(item, bytes):
                    show(item)
                else:
                    text["tm"] = mat_mul([1, 0, 0, 1, -float(item) / 1000 * text["size"] * text["th"], 0], text["tm"])
        elif op == "'":
            text["tm"] = text["tlm"] = mat_mul([1, 0, 0, 1, 0, -text["tl"]], text["tlm"])
            show(o[-1])
        elif op == "Do":
            raise ValueError("contains placed objects; export an SVG from Illustrator instead")
        operands = []

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {x1 - x0:.2f} {y1 - y0:.2f}">']
    for d, fill, stroke, lw, evenodd in shapes:
        attrs = f'fill="{fill or "none"}"'
        if stroke:
            attrs += f' stroke="{stroke}" stroke-width="{lw:.2f}"'
        if evenodd:
            attrs += ' fill-rule="evenodd"'
        parts.append(f'<path d="{d}" {attrs}/>')
    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------- recoloring

SVG_NS = "http://www.w3.org/2000/svg"
SHAPES = {"path", "rect", "circle", "ellipse", "polygon", "polyline", "line", "text", "tspan", "use"}
NAMED = {"black": "#000000", "white": "#ffffff", "none": "none"}


def parse_color(value):
    if value is None:
        return None
    v = value.strip().lower()
    v = NAMED.get(v, v)
    if v == "none" or v.startswith("url("):
        return "none"
    m = re.fullmatch(r"#([0-9a-f]{3})", v)
    if m:
        v = "#" + "".join(c * 2 for c in m.group(1))
    m = re.fullmatch(r"rgb\((\d+),\s*(\d+),\s*(\d+)\)", v)
    if m:
        v = "#%02x%02x%02x" % tuple(int(x) for x in m.groups())
    return v if re.fullmatch(r"#[0-9a-f]{6}", v) else None


def is_light(hex_color):
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.5


def css_rules(root):
    """Simple Illustrator-style CSS: .cls-1{fill:#fff;} → {'cls-1': {'fill': '#fff'}}"""
    rules = {}
    for style in root.iter(f"{{{SVG_NS}}}style"):
        for sel, body in re.findall(r"([^{}]+)\{([^}]*)\}", style.text or ""):
            props = dict((k.strip(), v.strip()) for k, v in re.findall(r"([\w-]+)\s*:\s*([^;]+)", body))
            for s in sel.split(","):
                s = s.strip()
                if s.startswith("."):
                    rules.setdefault(s[1:], {}).update(props)
        # Fill/stroke now come from explicit attributes, which CSS rules would override
        style.text = re.sub(r"(?<![\w-])(fill|stroke)\s*:[^;}]*;?", "", style.text or "")
    return rules


def recolor(svg_text, ink, inner):
    """Dark parts → ink. Light parts → inner (None = transparent). Returns (svg, had_inner)."""
    ET.register_namespace("", SVG_NS)
    root = ET.fromstring(svg_text)
    rules = css_rules(root)
    had_inner = False

    def walk(el, inherited):
        nonlocal had_inner
        tag = el.tag.split("}")[-1]
        props = dict(inherited)
        for cls in (el.get("class") or "").split():
            props.update({k: v for k, v in rules.get(cls, {}).items() if k in ("fill", "stroke")})
        for k in ("fill", "stroke"):
            if el.get(k) is not None:
                props[k] = el.get(k)
        style = el.get("style")
        if style:
            for k, v in re.findall(r"(?<![\w-])(fill|stroke)\s*:\s*([^;]+)", style):
                props[k] = v
            el.set("style", re.sub(r"(?<![\w-])(fill|stroke)\s*:[^;]*;?", "", style))

        if tag in SHAPES:
            light_keys = set()  # which of fill/stroke are light (inner) on this shape
            for k, default in (("fill", "#000000"), ("stroke", "none")):
                c = parse_color(props.get(k, default)) or default
                if c == "none":
                    el.set(k, "none")
                elif is_light(c):
                    had_inner = True
                    light_keys.add(k)
                    el.set(k, inner or "none")
                else:
                    el.set(k, ink)
            order.append((el, light_keys))
        for child in el:
            walk(child, props)

    order = []  # shapes in paint order: (element, is_light)
    walk(root, {})
    if inner is None and had_inner:
        knock_out(root, order)
    return ET.tostring(root, encoding="unicode"), had_inner


def knock_out(root, order):
    """
    Transparent inner: Illustrator paints the light parts ON TOP of solid dark shapes, so
    hiding them would just leave solid shapes. Instead, mask every dark shape with the light
    shapes painted after it, so they cut real holes.
    """
    parents = {child: parent for parent in root.iter() for child in parent}

    def chain(el):
        out, p = [], parents.get(el)
        while p is not None and p is not root:
            out.insert(0, p.get("transform") or "")
            p = parents.get(p)
        return [t for t in out if t]

    defs = ET.SubElement(root, f"{{{SVG_NS}}}defs")
    root.remove(defs)
    root.insert(0, defs)
    masks = {}

    for i, (el, light_keys) in enumerate(order):
        if light_keys and el.get("fill") == "none" and el.get("stroke") == "none":
            continue  # purely light shape: it becomes a hole, nothing to mask
        later = [(lel, lk) for lel, lk in order[i + 1 :] if lk]
        if not later:
            continue
        key = tuple(id(x) for x, _ in later)
        if key not in masks:
            mid = f"knockout{len(masks)}"
            mask = ET.SubElement(defs, f"{{{SVG_NS}}}mask", {"id": mid, "maskUnits": "userSpaceOnUse",
                                                            "x": "-100000", "y": "-100000", "width": "200000", "height": "200000"})
            ET.SubElement(mask, f"{{{SVG_NS}}}rect", {"x": "-100000", "y": "-100000", "width": "200000", "height": "200000", "fill": "#fff"})
            dark_chain = chain(el)
            for lel, lk in later:
                copy = ET.fromstring(ET.tostring(lel))
                # In a mask, black = hidden: only the light parts of the shape cut holes
                for k in ("fill", "stroke"):
                    copy.set(k, "#000" if k in lk else "none")
                copy.attrib.pop("class", None)
                copy.attrib.pop("id", None)
                light_chain = chain(lel)
                extra = light_chain[len(dark_chain):] if light_chain[: len(dark_chain)] == dark_chain else light_chain
                holder = mask
                for t in extra:
                    holder = ET.SubElement(holder, f"{{{SVG_NS}}}g", {"transform": t})
                holder.append(copy)
            masks[key] = mid
        # Wrap the dark shape in a masked group at the same spot in the tree
        parent = parents[el]
        idx = list(parent).index(el)
        wrapper = ET.Element(f"{{{SVG_NS}}}g", {"mask": f"url(#{masks[key]})"})
        parent.remove(el)
        wrapper.append(el)
        parent.insert(idx, wrapper)
        parents[el] = wrapper
        parents[wrapper] = parent

    # Purely light shapes are now just holes; drop them from the visible drawing
    for el, light_keys in order:
        if light_keys and el.get("fill") == "none" and el.get("stroke") == "none" and el in parents:
            parents[el].remove(el)


def render_png(svg_path, png_path, viewbox_width):
    density = max(72, int(96 * PNG_WIDTH / viewbox_width * 1.5))
    # -strip and the exclude-chunk define keep ImageMagick from writing any metadata
    # (software name, creation dates, etc.): the PNG holds only pixels.
    subprocess.run(
        ["magick", "-background", "none", "-density", str(density), svg_path, "-resize", f"{PNG_WIDTH}x",
         "-strip", "-define", "png:exclude-chunk=all", "-define", "png:include-chunk=tRNS,gAMA", png_path],
        check=True,
        capture_output=True,
    )


def load_sources(prefix):
    names = {}
    for f in sorted(os.listdir(SRC_DIR)):
        base, ext = os.path.splitext(f)
        if ext.lower() in (".svg", ".ai") and base.startswith((LOGO_PREFIX, BADGE_PREFIX)) and base.startswith(prefix):
            # .svg wins over .ai of the same name
            if ext.lower() == ".svg" or base not in names:
                names[base] = os.path.join(SRC_DIR, f)
    return names


def main():
    p = argparse.ArgumentParser(description="Make SVG + PNG color variants of the logos in _media/logos/.")
    p.add_argument("prefix", nargs="?", default="", help="only logos whose name starts with this")
    p.add_argument("--no-png", action="store_true", help="only write SVGs")
    args = p.parse_args()

    if not args.no_png and not shutil.which("magick"):
        sys.exit("ImageMagick ('magick') is needed for PNGs; install it or use --no-png")

    os.makedirs(OUT_DIR, exist_ok=True)
    sources = load_sources(args.prefix)
    if not sources:
        sys.exit(f"No .svg or .ai logos in {SRC_DIR} start with '{args.prefix}'")

    written = 0
    for name, path in sources.items():
        try:
            base_svg = ai_to_svg(path) if path.lower().endswith(".ai") else open(path, encoding="utf-8").read()
        except Exception as e:
            print(f"SKIP {os.path.basename(path)}: {e}")
            continue

        vb = re.search(r'viewBox="[-\d.]+[ ,]+[-\d.]+[ ,]+([\d.]+)', base_svg)
        vb_width = float(vb.group(1)) if vb else 1000

        _, has_inner = recolor(base_svg, "#000000", "#ffffff")
        is_badge = name.startswith(BADGE_PREFIX)
        if is_badge:
            combos = [(None, "#000000", None, "#ffffff")]  # black with white inner, no name suffix
        elif has_inner:
            combos = [
                (i, c, n, INNERS[n])
                for i, c in INKS.items()
                for n in INNERS_FOR_INK.get(i, DEFAULT_INNERS)
                if c != INNERS[n]
            ]
        else:
            combos = [(i, c, None, None) for i, c in INKS.items()]

        print(f"{os.path.basename(path)}: {len(combos)} variants")
        for ink_name, ink, inner_name, inner in combos:
            svg, _ = recolor(base_svg, ink, inner)
            out = name + (f"-{ink_name}" if ink_name else "") + (f"-{inner_name}" if inner_name else "")
            svg_path = os.path.join(OUT_DIR, out + ".svg")
            with open(svg_path, "w", encoding="utf-8") as fh:
                fh.write(svg)
            if not args.no_png:
                render_png(svg_path, os.path.join(OUT_DIR, out + ".png"), vb_width)
            written += 1

    print(f"Done. {written} variants in {os.path.relpath(OUT_DIR, ROOT_DIR)}")


if __name__ == "__main__":
    main()
