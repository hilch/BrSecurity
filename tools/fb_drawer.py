#!/usr/bin/env python3
"""Draw IEC 61131-3 function blocks from a *.fun file as SVG.

Parse every FUNCTION_BLOCK / FUNCTION definition in a B&R Automation Studio
``*.fun`` declaration file and emit a diagram and parameter-table SVG per definition.
Table columns share widths across all definitions; cell text wraps at 40 characters.

Variable section layout:
  * Area 1 (orange)  -> VAR_INPUT (left pins) and VAR_OUTPUT (right pins);
                        for a FUNCTION the return value is drawn as a right pin.
  * Area 2 (gray)    -> VAR_IN_OUT (drawn as both a left and a right pin).
    * Area 3           -> unused.

Internal VAR / temporary variables are not drawn.

Text width is measured with Windows GDI. On non-Windows hosts a rough estimate
is used instead.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# Drawing configuration
# --------------------------------------------------------------------------- #
@dataclass
class Config:
    font_name: str = "Arial"
    font_size: int = 8
    additional_fb_width: float = 40
    additional_fb_frame_dis: float = 10
    centered: bool = False
    color_scheme: str = "Functional"


# --------------------------------------------------------------------------- #
# Parsed function-block model
# --------------------------------------------------------------------------- #
@dataclass
class IO:
    name: str
    type: str
    description: str = ""


@dataclass
class FunctionBlock:
    name: str
    inputs: list[IO] = field(default_factory=list)       # area 1, left
    outputs: list[IO] = field(default_factory=list)      # area 1, right
    in_outs: list[IO] = field(default_factory=list)      # area 2, both sides


# --------------------------------------------------------------------------- #
# Text measurement
# --------------------------------------------------------------------------- #
class TextMeasurer:
    """Measure label width in pixels."""

    def __init__(self, font_name: str, font_size: int) -> None:
        self.font_name = font_name
        self.font_size = font_size
        self._gdi = None
        self.logpixelsy = 96
        if sys.platform == "win32":
            try:
                self._gdi = _GdiMeasurer(font_name)
                self.logpixelsy = self._gdi.logpixelsy
            except Exception:
                self._gdi = None

    def label_pixel(self, label: str, italic: bool = False, bold: bool = False) -> int:
        if self._gdi is not None:
            cx = self._gdi.text_width(label, self.font_size, italic, bold)
        else:
            # Fallback estimate when GDI is unavailable (non-Windows hosts).
            px_height = self.font_size * 96 / 72
            cx = int(round(len(label) * px_height * 0.52))
        return vba_round(cx / 1.25)


class _GdiMeasurer:
    """Measure text extent through the Windows GDI."""

    def __init__(self, font_name: str) -> None:
        import ctypes
        from ctypes import wintypes

        self.ctypes = ctypes
        self.font_name = font_name

        class LOGFONTW(ctypes.Structure):
            _fields_ = [
                ("lfHeight", wintypes.LONG),
                ("lfWidth", wintypes.LONG),
                ("lfEscapement", wintypes.LONG),
                ("lfOrientation", wintypes.LONG),
                ("lfWeight", wintypes.LONG),
                ("lfItalic", wintypes.BYTE),
                ("lfUnderline", wintypes.BYTE),
                ("lfStrikeOut", wintypes.BYTE),
                ("lfCharSet", wintypes.BYTE),
                ("lfOutPrecision", wintypes.BYTE),
                ("lfClipPrecision", wintypes.BYTE),
                ("lfQuality", wintypes.BYTE),
                ("lfPitchAndFamily", wintypes.BYTE),
                ("lfFaceName", ctypes.c_wchar * 32),
            ]

        class SIZE(ctypes.Structure):
            _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]

        self.LOGFONTW = LOGFONTW
        self.SIZE = SIZE
        self.gdi32 = ctypes.windll.gdi32
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32

        # LOGPIXELSY is device caps index 90.
        hdc0 = self.user32.GetDC(0)
        self.logpixelsy = self.gdi32.GetDeviceCaps(hdc0, 90)
        self.user32.ReleaseDC(0, hdc0)

    def text_width(self, text: str, font_size: int, italic: bool, bold: bool) -> int:
        ctypes = self.ctypes
        gdi32 = self.gdi32
        if not text:
            return 0

        hdc = gdi32.CreateDCW("DISPLAY", None, None, None)
        try:
            lf = self.LOGFONTW()
            lf.lfFaceName = self.font_name
            lf.lfHeight = -self.kernel32.MulDiv(font_size, self.logpixelsy, 72)
            lf.lfItalic = 1 if italic else 0
            lf.lfWeight = 800 if bold else 400
            hfont = gdi32.CreateFontIndirectW(ctypes.byref(lf))
            old = gdi32.SelectObject(hdc, hfont)
            size = self.SIZE()
            gdi32.GetTextExtentPoint32W(hdc, text, len(text), ctypes.byref(size))
            gdi32.SelectObject(hdc, old)
            gdi32.DeleteObject(hfont)
            return int(size.cx)
        finally:
            gdi32.DeleteDC(hdc)


# --------------------------------------------------------------------------- #
# Numeric helpers
# --------------------------------------------------------------------------- #
def vba_round(value: float) -> int:
    """Round to the nearest integer using ties-to-even."""
    return int(round(value))


def muldiv(number: int, numerator: int, denominator: int) -> int:
    """Windows MulDiv(): (number*numerator)/denominator, rounded half away from zero."""
    if denominator == 0:
        return -1
    value = number * numerator / denominator
    return int(math.floor(value + 0.5)) if value >= 0 else int(math.ceil(value - 0.5))


# --------------------------------------------------------------------------- #
# .fun parsing
# --------------------------------------------------------------------------- #
_COMMENT_RE = re.compile(r"\(\*.*?\*\)", re.DOTALL)
_BLOCK_RE = re.compile(
    r"\b(FUNCTION_BLOCK|FUNCTION)\b\s+(\w+)(?:\s*:\s*(\w+))?(.*?)\bEND_\1\b",
    re.DOTALL,
)
_ATTR_RE = re.compile(r"\{[^}]*\}")


def _mask_comments(text: str) -> str:
    return _COMMENT_RE.sub(
        lambda match: re.sub(r"[^\r\n]", " ", match.group()), text
    )


def _description(text: str) -> str:
    return " ".join(
        " ".join(match.group()[2:-2].split())
        for match in _COMMENT_RE.finditer(text)
        if not match.group()[2:-2].lstrip().startswith("$")
    ).strip()


def _section(body: str, keyword: str) -> list[IO]:
    """Return the IO entries of a VAR section (VAR_INPUT / VAR_OUTPUT / VAR_IN_OUT)."""
    masked = _mask_comments(body)
    match = re.search(rf"\b{keyword}\b(.*?)\bEND_VAR\b", masked, re.DOTALL)
    if not match:
        return []
    section = body[match.start(1):match.end(1)]
    declarations = list(re.finditer(r"(\w+)\s*:\s*([^;]+);", match.group(1)))
    items: list[IO] = []
    for index, declaration in enumerate(declarations):
        name, type_part = declaration.groups()
        type_str = _ATTR_RE.sub("", type_part).split(":=")[0].strip()
        end = declarations[index + 1].start() if index + 1 < len(declarations) else len(section)
        description = _description(section[declaration.start():end])
        if name and type_str:
            items.append(IO(name, type_str, description))
    return items


def parse_fun(text: str) -> list[FunctionBlock]:
    blocks: list[FunctionBlock] = []
    for match in _BLOCK_RE.finditer(_mask_comments(text)):
        kind, name, ret_type, _ = match.groups()
        body = text[match.start(4):match.end(4)]
        fb = FunctionBlock(name=name)
        fb.inputs = _section(body, "VAR_INPUT")
        fb.outputs = _section(body, "VAR_OUTPUT")
        fb.in_outs = _section(body, "VAR_IN_OUT")
        if kind == "FUNCTION" and ret_type:
            # A function returns through a right-side pin named like the function.
            header = re.split(r"\bVAR(?:_INPUT|_OUTPUT|_IN_OUT)?\b", _mask_comments(body))[0]
            fb.outputs.insert(0, IO(name, ret_type, _description(body[:len(header)])))
        blocks.append(fb)
    return blocks


# --------------------------------------------------------------------------- #
# SVG generation
# --------------------------------------------------------------------------- #
def _xml_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_GRADIENTS = """\
        <linearGradient
            id="linearGradient_FB_Header"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="0%">
            <stop offset="0%" stop-color="#5cacee"/>
            <stop offset="50%" stop-color="#ccdff8"/>
            <stop offset="100%" stop-color="#ffffff"/>
        </linearGradient>
        <linearGradient
            id="linearGradient_FB_Header_Safety"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="0%">
            <stop offset="0%" stop-color="#ffff00"/>
            <stop offset="50%" stop-color="#ffffcc"/>
            <stop offset="100%" stop-color="#ffffff"/>
        </linearGradient>
        <linearGradient
            id="linearGradient_FB_Header_SafeDESIGNER"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="0%">
            <stop offset="0%" stop-color="#ffff00"/>
            <stop offset="50%" stop-color="#ffff00"/>
            <stop offset="100%" stop-color="#ffff00"/>
        </linearGradient>
        <linearGradient
            id="linearGradient_FB_BodyArea_1"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="0%">
            <stop offset="0%" stop-color="#ff7f00"/>
            <stop offset="50%" stop-color="#ffc8b6"/>
            <stop offset="100%" stop-color="#ffffff"/>
        </linearGradient>
        <linearGradient
            id="linearGradient_FB_BodyArea_1_Safety"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="0%">
            <stop offset="0%" stop-color="#ffff00"/>
            <stop offset="50%" stop-color="#ffffcc"/>
            <stop offset="100%" stop-color="#ffffff"/>
        </linearGradient>
        <linearGradient
            id="linearGradient_FB_BodyArea_1_SafeDESIGNER"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="0%">
            <stop offset="0%" stop-color="#ffff00"/>
            <stop offset="50%" stop-color="#ffff00"/>
            <stop offset="100%" stop-color="#ffff00"/>
        </linearGradient>
        <linearGradient
            id="linearGradient_FB_BodyArea_2"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="0%">
            <stop offset="0%" stop-color="#bebebe"/>
            <stop offset="50%" stop-color="#e4e4e4"/>
            <stop offset="100%" stop-color="#ffffff"/>
        </linearGradient>
"""


def render_svg(fb: FunctionBlock, cfg: Config, measurer: TextMeasurer) -> str:
    font = cfg.font_name
    size = cfg.font_size
    frame = cfg.additional_fb_frame_dis

    # --- base metrics ----------------------------------------------------- #
    fb_font_height = vba_round(muldiv(size, measurer.logpixelsy, 72) / 1.25)
    fb_header_height = vba_round(fb_font_height * 1.8)
    fb_io_height = fb_header_height
    fb_io_line = fb_font_height * 2
    fb_baseline = vba_round(-fb_font_height * 0.55)

    # --- collect pin lists per drawing area ------------------------------- #
    in1, out1 = fb.inputs, fb.outputs
    in2, out2 = fb.in_outs, fb.in_outs

    max_name = lambda ios: max((measurer.label_pixel(io.name) for io in ios), default=0)
    max_type = lambda ios: max((measurer.label_pixel(io.type) for io in ios), default=0)

    max_fb_name = measurer.label_pixel(fb.name)
    max_in_name = max(max_name(in1), max_name(in2))
    max_in_type = max(max_type(in1), max_type(in2))
    max_out_name = max(max_name(out1), max_name(out2))
    max_out_type = max(max_type(out1), max_type(out2))

    if cfg.centered:
        if max_in_type > max_out_type:
            max_out_type = max_in_type
        else:
            max_in_type = max_out_type

    # --- x geometry ------------------------------------------------------- #
    fb_body_x = vba_round(max_in_type + fb_io_line * 1.5 + frame)
    if (max_in_name + max_out_name + fb_io_line) < max_fb_name:
        fb_width = vba_round(max_fb_name + fb_io_line + cfg.additional_fb_width)
    else:
        fb_width = vba_round(max_in_name + max_out_name + fb_io_line + cfg.additional_fb_width)
    fb_header_x = vba_round(fb_body_x + fb_width / 2)
    fb_svg_width = vba_round(
        max_in_type + 1.5 * fb_io_line + fb_width + 1.5 * fb_io_line + max_out_type
    ) + 1 + frame * 2

    # --- y geometry ------------------------------------------------------- #
    area1_h = fb_io_height * max(len(in1), len(out1))
    area2_h = fb_io_height * max(len(in2), len(out2))
    area3_h = 0
    fb_body_h = area1_h + area2_h + area3_h
    fb_svg_height = fb_body_h + fb_header_height + 2 + frame * 2

    header_fill = {
        "Functional": "linearGradient_FB_Header",
        "Safety": "linearGradient_FB_Header_Safety",
    }.get(cfg.color_scheme, "linearGradient_FB_Header_SafeDESIGNER")
    area1_fill = {
        "Functional": "linearGradient_FB_BodyArea_1",
        "Safety": "linearGradient_FB_BodyArea_1",
    }.get(cfg.color_scheme, "linearGradient_FB_BodyArea_1_SafeDESIGNER")

    def i(value: float) -> str:
        return str(int(value))

    out: list[str] = []
    add = out.append

    add('<?xml version="1.0" encoding="UTF-8" standalone="no"?>')
    add('<svg version="1.1"')
    add('    xmlns="http://www.w3.org/2000/svg"')
    add('    xmlns:xlink="http://www.w3.org/1999/xlink"')
    add(f'    width="{i(fb_svg_width)}px"')
    add(f'    height="{i(fb_svg_height)}px">')
    add("    <defs>")
    add(_GRADIENTS.rstrip("\n"))
    add(f'        <rect id="FB_Header" height="{i(fb_header_height)}px" '
        f'width="{i(fb_width)}px" fill="url(#{header_fill})" stroke="black"/>')
    add(f'        <rect id="FB_Body" height="{i(fb_body_h)}px" '
        f'width="{i(fb_width)}px" fill="#ffffff"/>')
    add(f'        <rect id="FB_BodyArea1" height="{i(area1_h)}px" '
        f'width="{i(fb_width)}px" fill="url(#{area1_fill})"/>')
    add(f'        <rect id="FB_BodyArea2" height="{i(area2_h)}px" '
        f'width="{i(fb_width)}px" fill="url(#linearGradient_FB_BodyArea_2)"/>')
    add(f'        <rect id="FB_BodyFrame" '
        f'height="{i(fb_header_height + area1_h + area2_h + area3_h)}px" '
        f'width="{i(fb_width)}px" stroke="black" style="fill:none;fill-opacity:1"/>')
    add("    </defs>")

    body_top = 1 + frame + fb_header_height
    add(f'    <use x="{i(fb_body_x)}px" y="{i(body_top)}px" xlink:href="#FB_Body"/>')
    add(f'    <use x="{i(fb_body_x)}px" y="{i(body_top)}px" xlink:href="#FB_BodyArea1"/>')
    add(f'    <use x="{i(fb_body_x)}px" y="{i(body_top + area1_h)}px" xlink:href="#FB_BodyArea2"/>')
    add(f'    <use x="{i(fb_body_x)}px" y="{i(1 + frame)}px" xlink:href="#FB_BodyFrame"/>')
    add(f'    <use x="{i(fb_body_x)}px" y="{i(1 + frame)}px" xlink:href="#FB_Header"/>')

    # FB header text
    hy = 1 + frame + vba_round(fb_header_height + fb_baseline)
    add(f'    <text x="{i(fb_header_x)}px" y="{i(hy)}px" '
        f'style="font-size:{i(vba_round(size))}px;fill:#000000;font-family:{font};'
        f'text-anchor:middle;writing-mode:lr">{_xml_escape(fb.name)}</text>')

    def draw_inputs(ios: list[IO], area_offset: int) -> None:
        for count, io in enumerate(ios):
            ly = 1 + frame + vba_round(fb_header_height + area_offset + fb_io_height / 2 + fb_io_height * count)
            ty = 1 + frame + vba_round(fb_header_height + area_offset + fb_io_height * (1 + count) + fb_baseline)
            add(f'    <path d="M {i(fb_body_x - fb_io_line)},{i(ly)},{i(fb_body_x)},{i(ly)}" stroke="black"/>')
            add(f'    <text x="{i(fb_body_x - fb_io_line * 1.5)}px" y="{i(ty)}px" '
                f'style="font-size:{i(vba_round(size))}px;fill:#000000;font-family:{font};'
                f'text-anchor:end;writing-mode:lr">{_xml_escape(io.type)}</text>')
            add(f'    <text x="{i(fb_body_x + fb_io_line / 2)}px" y="{i(ty)}px" '
                f'style="font-size:{i(vba_round(size))}px;fill:#000000;font-family:{font};'
                f'text-anchor:start;writing-mode:lr">{_xml_escape(io.name)}</text>')

    def draw_outputs(ios: list[IO], area_offset: int) -> None:
        for count, io in enumerate(ios):
            ly = 1 + frame + vba_round(fb_header_height + area_offset + fb_io_height / 2 + fb_io_height * count)
            ty = 1 + frame + vba_round(fb_header_height + area_offset + fb_io_height * (1 + count) + fb_baseline)
            add(f'    <path d="M {i(fb_body_x + fb_width)},{i(ly)},'
                f'{i(fb_body_x + fb_width + fb_io_line)},{i(ly)}" stroke="black"/>')
            add(f'    <text x="{i(fb_body_x + fb_width + fb_io_line * 1.5)}px" y="{i(ty)}px" '
                f'style="font-size:{i(vba_round(size))}px;fill:#000000;font-family:{font};'
                f'text-anchor:start;writing-mode:lr">{_xml_escape(io.type)}</text>')
            add(f'    <text x="{i(fb_body_x + fb_width - fb_io_line / 2)}px" y="{i(ty)}px" '
                f'style="font-size:{i(vba_round(size))}px;fill:#000000;font-family:{font};'
                f'text-anchor:end;writing-mode:lr">{_xml_escape(io.name)}</text>')

    draw_inputs(in1, 0)
    draw_inputs(in2, area1_h)
    draw_outputs(out1, 0)
    draw_outputs(out2, area1_h)

    add("</svg>")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# Parameter tables
# --------------------------------------------------------------------------- #
_TABLE_HEADERS = ("Parameter", "Datatype", "Description")
_TABLE_PADDING = 8


def _table_lines(text: str) -> list[str]:
    return textwrap.wrap(text, width=40, break_long_words=True, break_on_hyphens=False) or [""]


def table_column_widths(blocks: list[FunctionBlock], measurer: TextMeasurer) -> list[int]:
    widths = [math.ceil(measurer.label_pixel(header, bold=True) * 1.25)
              for header in _TABLE_HEADERS]
    for fb in blocks:
        for io in fb.inputs + fb.outputs + fb.in_outs:
            for column, value in enumerate((io.name, io.type, io.description)):
                for line in _table_lines(value):
                    widths[column] = max(widths[column], math.ceil(measurer.label_pixel(line) * 1.25))
    return [width + 2 * _TABLE_PADDING for width in widths]


def render_table_svg(fb: FunctionBlock, cfg: Config, widths: list[int]) -> str:
    line_height = math.ceil(cfg.font_size * 1.5)
    rows: list[tuple[list[list[str]], str, bool]] = [
        ([[_TABLE_HEADERS[column]] for column in range(3)], "#dce9f5", True)
    ]
    for label, ios in (("Inputs", fb.inputs), ("Outputs", fb.outputs), ("In/Out", fb.in_outs)):
        if not ios:
            continue
        rows.append(([[label]], "#eeeeee", True))
        for io in ios:
            rows.append(([_table_lines(value) for value in (io.name, io.type, io.description)],
                         "#ffffff", False))
    height = sum(max(map(len, cells)) * line_height + 2 * _TABLE_PADDING
                 for cells, _, _ in rows)
    width = sum(widths)
    root = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": f"{width + 2}px", "height": f"{height + 2}px",
        "viewBox": f"0 0 {width + 2} {height + 2}",
        "font-family": cfg.font_name, "font-size": str(cfg.font_size),
    })
    ET.SubElement(root, "title").text = f"{fb.name} parameters"
    top = 1
    for cells, fill, bold in rows:
        row_height = max(map(len, cells)) * line_height + 2 * _TABLE_PADDING
        left = 1
        for column, lines in enumerate(cells):
            cell_width = width if len(cells) == 1 else widths[column]
            ET.SubElement(root, "rect", {
                "x": str(left), "y": str(top), "width": str(cell_width),
                "height": str(row_height), "fill": fill, "stroke": "#999999",
            })
            text = ET.SubElement(root, "text", {
                "font-weight": "bold" if bold else "normal", "fill": "#000000",
            })
            for index, line in enumerate(lines):
                ET.SubElement(text, "tspan", {
                    "x": str(left + _TABLE_PADDING),
                    "y": str(top + _TABLE_PADDING + cfg.font_size + index * line_height),
                }).text = line
            left += cell_width
        top += row_height
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Draw IEC 61131-3 function blocks as SVG.")
    parser.add_argument("fun", help="path to the *.fun declaration file")
    parser.add_argument("-o", "--outdir", required=True,
                        help="output directory")
    parser.add_argument("--font", default=Config.font_name)
    parser.add_argument("--font-size", type=int, default=Config.font_size)
    parser.add_argument("--additional-width", type=float, default=Config.additional_fb_width)
    parser.add_argument("--frame-distance", type=float, default=Config.additional_fb_frame_dis)
    parser.add_argument("--centered", action="store_true")
    parser.add_argument("--color-scheme", default=Config.color_scheme,
                        choices=["Functional", "Safety", "SafeDESIGNER"])
    args = parser.parse_args(argv)

    if not os.path.isfile(args.fun):
        print(f"error: file not found: {args.fun}", file=sys.stderr)
        return 1

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    cfg = Config(
        font_name=args.font,
        font_size=args.font_size,
        additional_fb_width=args.additional_width,
        additional_fb_frame_dis=args.frame_distance,
        centered=args.centered,
        color_scheme=args.color_scheme,
    )
    measurer = TextMeasurer(cfg.font_name, cfg.font_size)

    with open(args.fun, "r", encoding="utf-8-sig") as handle:
        text = handle.read()

    blocks = parse_fun(text)
    if not blocks:
        print("warning: no FUNCTION or FUNCTION_BLOCK definitions found", file=sys.stderr)
        return 1

    widths = table_column_widths(blocks, measurer)
    for fb in blocks:
        for filename, svg in (
            (f"{fb.name}.svg", render_svg(fb, cfg, measurer)),
            (f"{fb.name}_table.svg", render_table_svg(fb, cfg, widths)),
        ):
            path = os.path.join(outdir, filename)
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(svg)
            print(f"wrote {path}")

    print(f"\n{2 * len(blocks)} SVG file(s) generated in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
