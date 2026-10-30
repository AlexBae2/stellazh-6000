"""Минимальный, но совместимый с Visio генератор .vsdx (OOXML/OPC).

Собран по структуре настоящего файла Visio: [Content_Types].xml + _rels + visio/{document,pages,pageN}.
Геометрия каждого примитива лежит в собственной секции Geometry фигуры, поэтому
в Visio чертёж остаётся редактируемым (линии, прямоугольники, текст, дуги).

Единицы: снаружи — миллиметры листа, начало координат в левом верхнем углу,
ось Y вниз (как на бумаге). Внутри Visio — дюймы и ось Y вверх.
"""
from __future__ import annotations

import html
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from PIL import ImageFont

MM = 1.0 / 25.4
A3_W, A3_H = 420.0, 297.0

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Narrow.ttf",
    "/Library/Fonts/Arial.ttf",
]
_font = None
for _p in _FONT_CANDIDATES:
    try:
        _font = ImageFont.truetype(_p, 100)
        break
    except OSError:
        continue


def num(v: float) -> str:
    """Число для XML: точка-разделитель, без хвостовых нулей."""
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def text_width_mm(s: str, size_mm: float, bold: bool = False) -> float:
    """Ширина строки в мм для Arial при кегле size_mm (em)."""
    if _font is None:
        return len(s) * size_mm * 0.55
    w = sum(_font.getlength(ch) for ch in s) / 100.0 * size_mm
    return w * (1.04 if bold else 1.0)


def esc(s: str) -> str:
    return html.escape(s, quote=False)


class Page:
    def __init__(self, name: str, w: float = A3_W, h: float = A3_H, scale: float = 1.0):
        self.name = name
        self.w = w
        self.h = h
        self.scale = scale  # 1:scale on paper
        self._shapes: list[str] = []
        self._id = 0
        self._order: list[tuple[int, str]] = []
        self._z = 0
        self.items: list[tuple] = []

    # ---------- служебное ----------
    def _shape(self, body: str, z: int | None = None) -> None:
        self._id += 1
        self._z += 1
        self._shapes.append((z if z is not None else self._z, body.replace("@ID@", str(self._id))))

    def _px(self, x: float) -> float:
        return x * MM

    def _py(self, y: float) -> float:
        return (self.h - y) * MM

    # ---------- примитивы ----------
    def poly(self, pts, lw: float = 0.35, fill: str | None = None, dash: int | None = None,
             close: bool = True, z: int | None = None) -> None:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        bx, by = min(xs), min(ys)
        bw = max(max(xs) - bx, 0.02)
        bh = max(max(ys) - by, 0.02)
        rows = []
        for i, (x, y) in enumerate(pts):
            t = "MoveTo" if i == 0 else "LineTo"
            lx = (x - bx) * MM
            ly = (by + bh - y) * MM
            rows.append(
                f"<Row T='{t}' IX='{i + 1}'><Cell N='X' V='{num(lx)}'/><Cell N='Y' V='{num(ly)}'/></Row>"
            )
        if close and pts[0] != pts[-1]:
            rows.append(
                f"<Row T='LineTo' IX='{len(pts) + 1}'>"
                f"<Cell N='X' V='{num((pts[0][0] - bx) * MM)}'/>"
                f"<Cell N='Y' V='{num((by + bh - pts[0][1]) * MM)}'/></Row>"
            )
        self.items.append(("line", tuple(pts), lw))
        no_line = 1 if lw <= 0 else 0
        geom = (
            f"<Section N='Geometry' IX='0'><Cell N='NoFill' V='{0 if fill else 1}'/>"
            f"<Cell N='NoLine' V='{no_line}'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>"
            f"<Cell N='NoQuickDrag' V='0'/>{''.join(rows)}</Section>"
        )
        props = (
            f"<Cell N='LineWeight' V='{num(lw * MM)}'/><Cell N='LineColor' V='{'#000000'}'/>"
            f"<Cell N='LinePattern' V='{dash or 1}'/>"
            f"<Cell N='FillPattern' V='{1 if fill else 0}'/><Cell N='FillForegnd' V='{fill or '#FFFFFF'}'/>"
        )
        self._shape(self._wrap(bx, by, bw, bh, 0.0, props + geom), z)

    def line(self, x1, y1, x2, y2, lw: float = 0.25, dash: int | None = None, z=None) -> None:
        self.poly([(x1, y1), (x2, y2)], lw=lw, dash=dash, z=z)

    def rect(self, x, y, w, h, lw: float = 0.35, fill: str | None = None,
             dash: int | None = None, z=None) -> None:
        self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], lw=lw, fill=fill, dash=dash, z=z)

    def circle(self, cx, cy, r, lw: float = 0.3, fill: str | None = None, z=None) -> None:
        import math
        pts = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in
               [2 * math.pi * i / 24 for i in range(25)]]
        self.poly(pts, lw=lw, fill=fill, z=z)

    def arc(self, cx, cy, r, a0_deg, a1_deg, lw: float = 0.2, dash: int | None = None, z=None) -> None:
        """Дуга по часовой стрелке (в экранных координатах Y вниз)."""
        import math
        a0, a1 = math.radians(a0_deg), math.radians(a1_deg)
        n = 24
        pts = [(cx + r * math.cos(a0 + (a1 - a0) * i / n),
                cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
        self.poly(pts, lw=lw, dash=dash, close=False, z=z)

    def text(self, x, y, s, size: float = 3.5, align: str = "left", bold: bool = False,
             italic: bool = False, angle: float = 0.0, color: str = "#000000",
             valign: str = "top", width: float | None = None, lines: int = 1, z=None) -> None:
        if not s:
            return
        est = text_width_mm(s, size, bold) * 1.10 + 0.6
        w = width if width else est
        h = size * 1.55 * max(1, lines)
        if align == "left":
            bx = x
        elif align == "center":
            bx = x - w / 2
        else:  # right
            bx = x - w
        if valign == "top":
            by = y
        elif valign == "middle":
            by = y - h / 2
        else:
            by = y - h
        vis = min(est, width) if width else est
        if align == "left":
            tx0, tx1 = x, x + vis
        elif align == "center":
            tx0, tx1 = x - vis / 2, x + vis / 2
        else:
            tx0, tx1 = x - vis, x
        th = size * 1.15
        if valign == "top":
            ty0, ty1 = y, y + th
        elif valign == "middle":
            ty0, ty1 = y - th / 2, y + th / 2
        else:
            ty0, ty1 = y - th, y
        self.items.append(("text", (tx0, ty0, tx1, ty1), s, size, angle))
        style = (1 if bold else 0) | (2 if italic else 0)
        halign = {"left": 0, "center": 1, "right": 2, "justify": 3}[align]
        body = (
            f"<Cell N='LineWeight' V='0'/><Cell N='LinePattern' V='0'/>"
            f"<Cell N='FillPattern' V='0'/><Cell N='VerticalAlign' V='1'/>"
            f"<Cell N='LeftMargin' V='0'/><Cell N='RightMargin' V='0'/>"
            f"<Cell N='TopMargin' V='0'/><Cell N='BottomMargin' V='0'/>"
            f"<Section N='Character'><Row IX='0'><Cell N='Font' V='Arial'/><Cell N='Color' V='{color}'/>"
            f"<Cell N='Style' V='{style}'/><Cell N='Size' V='{num(size * MM)}'/></Row></Section>"
            f"<Section N='Paragraph'><Row IX='0'><Cell N='HorzAlign' V='{halign}'/></Row></Section>"
            f"<Text>{esc(s)}</Text>"
        )
        self._shape(self._wrap(bx, by, w, h, angle, body), z)

    def _wrap(self, bx, by, bw, bh, angle, body) -> str:
        w = bw * MM
        h = bh * MM
        pinx = (bx + bw / 2) * MM
        piny = (self.h - (by + bh / 2)) * MM
        head = (
            f"<Shape ID='@ID@' Type='Shape' LineStyle='0' FillStyle='0' TextStyle='0'>"
            f"<Cell N='PinX' V='{num(pinx)}'/><Cell N='PinY' V='{num(piny)}'/>"
            f"<Cell N='Width' V='{num(w)}'/><Cell N='Height' V='{num(h)}'/>"
            f"<Cell N='LocPinX' V='{num(w / 2)}' F='Width*0.5'/><Cell N='LocPinY' V='{num(h / 2)}' F='Height*0.5'/>"
            f"<Cell N='Angle' V='{num(angle)}'/><Cell N='FlipX' V='0'/><Cell N='FlipY' V='0'/>"
            f"<Cell N='ResizeMode' V='0'/><Cell N='ObjType' V='1'/>"
        )
        return head + body + "</Shape>"

    # ---------- сборка страницы ----------
    def xml(self) -> str:
        shapes = "".join(body for _z, body in sorted(self._shapes, key=lambda t: t[0]))
        return (
            "<?xml version='1.0' encoding='utf-8' ?>\n"
            "<PageContents xmlns='http://schemas.microsoft.com/office/visio/2012/main' "
            "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' "
            "xml:space='preserve'><Shapes>" + shapes + "</Shapes></PageContents>"
        )


PAGE_REL = "http://schemas.microsoft.com/visio/2010/relationships/page"


class Document:
    def __init__(self, pages: list[Page], title: str = "", creator: str = ""):
        self.pages = pages
        self.title = title
        self.creator = creator
        self.skeleton = Path(__file__).with_name("skeleton")

    def _content_types(self) -> str:
        pages = "".join(
            f"<Override PartName='/visio/pages/page{i + 1}.xml' "
            f"ContentType='application/vnd.ms-visio.page+xml'/>"
            for i in range(len(self.pages))
        )
        return (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
            "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
            "<Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>"
            "<Default Extension='xml' ContentType='application/xml'/>"
            "<Override PartName='/visio/document.xml' ContentType='application/vnd.ms-visio.drawing.main+xml'/>"
            "<Override PartName='/visio/masters/masters.xml' ContentType='application/vnd.ms-visio.masters+xml'/>"
            "<Override PartName='/visio/pages/pages.xml' ContentType='application/vnd.ms-visio.pages+xml'/>"
            + pages +
            "<Override PartName='/visio/windows.xml' ContentType='application/vnd.ms-visio.windows+xml'/>"
            "<Override PartName='/docProps/core.xml' ContentType='application/vnd.openxmlformats-package.core-properties+xml'/>"
            "<Override PartName='/docProps/app.xml' ContentType='application/vnd.openxmlformats-officedocument.extended-properties+xml'/>"
            "</Types>"
        )

    def _root_rels(self) -> str:
        return (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
            "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
            "<Relationship Id='rId1' Type='http://schemas.microsoft.com/visio/2010/relationships/document' Target='visio/document.xml'/>"
            "<Relationship Id='rId2' Type='http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties' Target='docProps/core.xml'/>"
            "<Relationship Id='rId3' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties' Target='docProps/app.xml'/>"
            "</Relationships>"
        )

    def _document_rels(self) -> str:
        return (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
            "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
            "<Relationship Id='rId1' Type='http://schemas.microsoft.com/visio/2010/relationships/pages' Target='pages/pages.xml'/>"
            "<Relationship Id='rId2' Type='http://schemas.microsoft.com/visio/2010/relationships/masters' Target='masters/masters.xml'/>"
            "<Relationship Id='rId3' Type='http://schemas.microsoft.com/visio/2010/relationships/windows' Target='windows.xml'/>"
            "</Relationships>"
        )

    def _masters(self) -> str:
        return (
            "<?xml version='1.0' encoding='utf-8' ?>\n"
            "<Masters xmlns='http://schemas.microsoft.com/office/visio/2012/main' "
            "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' "
            "xml:space='preserve' />"
        )

    def _pages_xml(self) -> str:
        out = []
        for i, p in enumerate(self.pages):
            scale = p.scale
            out.append(
                f"<Page ID='{i}' NameU='{esc(p.name)}' Name='{esc(p.name)}' ViewScale='1' "
                f"ViewCenterX='{num(p.w * MM / 2)}' ViewCenterY='{num(p.h * MM / 2)}'>"
                "<PageSheet LineStyle='0' FillStyle='0' TextStyle='0'>"
                f"<Cell N='PageWidth' V='{num(p.w * MM)}'/><Cell N='PageHeight' V='{num(p.h * MM)}'/>"
                f"<Cell N='ShdwOffsetX' V='{num(3 * MM)}'/><Cell N='ShdwOffsetY' V='{num(-3 * MM)}'/>"
                f"<Cell N='PageScale' V='{num(1 * MM)}' U='MM'/>"
                f"<Cell N='DrawingScale' V='{num(scale * MM)}' U='MM'/>"
                "<Cell N='DrawingSizeType' V='0'/><Cell N='DrawingScaleType' V='0'/>"
                "<Cell N='InhibitSnap' V='0'/><Cell N='UIVisibility' V='0'/><Cell N='ShdwType' V='0'/>"
                "<Cell N='ShdwObliqueAngle' V='0'/><Cell N='ShdwScaleFactor' V='1'/>"
                "<Cell N='DrawingResizeType' V='1'/></PageSheet>"
                f"<Rel r:id='rId{i + 1}'/></Page>"
            )
        return (
            "<?xml version='1.0' encoding='utf-8' ?>\n"
            "<Pages xmlns='http://schemas.microsoft.com/office/visio/2012/main' "
            "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' "
            "xml:space='preserve'>" + "".join(out) + "</Pages>"
        )

    def _pages_rels(self) -> str:
        rels = "".join(
            f"<Relationship Id='rId{i + 1}' Type='{PAGE_REL}' Target='page{i + 1}.xml'/>"
            for i in range(len(self.pages))
        )
        return (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
            "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
            + rels + "</Relationships>"
        )

    def _core(self) -> str:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
            "<cp:coreProperties xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties' "
            "xmlns:dc='http://purl.org/dc/elements/1.1/' xmlns:dcterms='http://purl.org/dc/terms/' "
            "xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'>"
            f"<dc:title>{esc(self.title)}</dc:title><dc:creator>{esc(self.creator)}</dc:creator>"
            f"<dcterms:created xsi:type='dcterms:W3CDTF'>{now}</dcterms:created>"
            f"<dcterms:modified xsi:type='dcterms:W3CDTF'>{now}</dcterms:modified>"
            "<dc:language>ru-RU</dc:language></cp:coreProperties>"
        )

    def _app(self) -> str:
        return (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
            "<Properties xmlns='http://schemas.openxmlformats.org/officeDocument/2006/extended-properties' "
            "xmlns:vt='http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes'>"
            "<Application>Microsoft Visio</Application><ScaleCrop>false</ScaleCrop>"
            f"<HeadingPairs><vt:vector size='2' baseType='variant'><vt:variant><vt:lpstr>Pages</vt:lpstr></vt:variant>"
            f"<vt:variant><vt:i4>{len(self.pages)}</vt:i4></vt:variant></vt:vector></HeadingPairs>"
            f"<TitlesOfParts><vt:vector size='{len(self.pages)}' baseType='lpstr'>"
            + "".join(f"<vt:lpstr>{esc(p.name)}</vt:lpstr>" for p in self.pages)
            + "</vt:vector></TitlesOfParts><AppVersion>16.0000</AppVersion></Properties>"
        )

    def _windows(self) -> str:
        wins = []
        for i, p in enumerate(self.pages):
            wins.append(
                f"<Window ID='{i}' WindowType='Drawing' WindowState='1073741824' WindowLeft='-9' "
                f"WindowTop='-38' WindowWidth='1938' WindowHeight='854' ContainerType='Page' Page='{i}' "
                f"ViewScale='0.6' ViewCenterX='{num(p.w * MM / 2)}' ViewCenterY='{num(p.h * MM / 2)}'>"
                "<ShowRulers>1</ShowRulers><ShowGrid>0</ShowGrid><ShowPageBreaks>0</ShowPageBreaks>"
                "<ShowGuides>1</ShowGuides><ShowConnectionPoints>1</ShowConnectionPoints>"
                "<GlueSettings>9</GlueSettings><SnapSettings>65847</SnapSettings><SnapExtensions>34</SnapExtensions>"
                "<SnapAngles/><DynamicGridEnabled>1</DynamicGridEnabled><TabSplitterPos>0.5</TabSplitterPos></Window>"
            )
        return (
            "<?xml version='1.0' encoding='utf-8' ?>\n"
            "<Windows ClientWidth='1920' ClientHeight='807' "
            "xmlns='http://schemas.microsoft.com/office/visio/2012/main' "
            "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' "
            "xml:space='preserve'>" + "".join(wins) + "</Windows>"
        )

    def save(self, path: str) -> str:
        document = (self.skeleton / "document.xml").read_text(encoding="utf-8")
        parts = {
            "[Content_Types].xml": self._content_types(),
            "_rels/.rels": self._root_rels(),
            "docProps/core.xml": self._core(),
            "docProps/app.xml": self._app(),
            "visio/document.xml": document,
            "visio/_rels/document.xml.rels": self._document_rels(),
            "visio/masters/masters.xml": self._masters(),
            "visio/pages/pages.xml": self._pages_xml(),
            "visio/pages/_rels/pages.xml.rels": self._pages_rels(),
            "visio/windows.xml": self._windows(),
        }
        for i, p in enumerate(self.pages):
            parts[f"visio/pages/page{i + 1}.xml"] = p.xml()
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            # [Content_Types].xml первым — так делают все офисные пакеты
            for name in sorted(parts, key=lambda n: (n != "[Content_Types].xml", n)):
                z.writestr(name, parts[name])
        return path
