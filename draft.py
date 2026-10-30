"""Чертёжные примитивы поверх vsd.Page: рамка, основная надпись, размеры, таблицы.

Всё в миллиметрах листа; оси как на бумаге (Y вниз).
"""
from __future__ import annotations

import math

from vsd import A3_H, A3_W, Page, text_width_mm

LW_THIN = 0.15
LW_MAIN = 0.35
LW_BOLD = 0.55

S_TEXT = 2.5
S_DIM = 3.0
S_CAPTION = 2.0


def clip_line(x, y, w, h, x1, y1, x2, y2):
    """Отрезок внутри прямоугольника (Лян-Барски). None, если снаружи."""
    dx, dy = x2 - x1, y2 - y1
    p = (-dx, dx, -dy, dy)
    q = (x1 - x, x + w - x1, y1 - y, y + h - y1)
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if abs(pi) < 1e-12:
            if qi < 0:
                return None
            continue
        t = qi / pi
        if pi < 0:
            u1 = max(u1, t)
        else:
            u2 = min(u2, t)
        if u1 > u2:
            return None
    return (x1 + u1 * dx, y1 + u1 * dy, x1 + u2 * dx, y1 + u2 * dy)


class Sheet(Page):
    """Лист A3 с рамкой и штампом."""

    LEFT, TOP, RIGHT, BOTTOM = 20.0, 5.0, 415.0, 292.0

    def __init__(self, name: str, w: float = A3_W, h: float = A3_H):
        super().__init__(name, w, h, 1.0)
        self.frame()

    # ---------- рамка ----------
    def frame(self):
        self.rect(self.LEFT, self.TOP, self.RIGHT - self.LEFT, self.BOTTOM - self.TOP, lw=0.7)

    # ---------- размеры ----------
    def _arrow_h(self, x, y, direction):
        d = 3.0 if direction > 0 else -3.0
        self.poly([(x, y), (x + d, y - 1.0), (x + d, y + 1.0)], lw=0.0, fill="#000000")

    def _arrow_v(self, x, y, direction):
        d = 3.0 if direction > 0 else -3.0
        self.poly([(x, y), (x - 1.0, y + d), (x + 1.0, y + d)], lw=0.0, fill="#000000")

    def dim_h(self, x1, x2, y, text, obj_y=None, size=S_DIM, side="above", dash=None):
        self.line(x1, obj_y if obj_y is not None else y, x1, y + (-2 if side == "above" else 2), LW_THIN, dash=dash)
        self.line(x2, obj_y if obj_y is not None else y, x2, y + (-2 if side == "above" else 2), LW_THIN, dash=dash)
        gap = 1.0
        if abs(x2 - x1) > 12:
            self.line(x1, y, x2, y, LW_THIN, dash=dash)
            self._arrow_h(x1, y, +1)
            self._arrow_h(x2, y, -1)
        else:
            self.line(x1, y, x2, y, LW_THIN, dash=dash)
        ty = y - 1.2 if side == "above" else y + size + 0.4
        self.text((x1 + x2) / 2, ty, text, size, "center", valign="bottom" if side == "above" else "top")

    def dim_v(self, x, y1, y2, text, obj_x=None, size=S_DIM, side="left"):
        xo = obj_x if obj_x is not None else x
        self.line(xo, y1, x + (-2 if side == "left" else 2), y1, LW_THIN)
        self.line(xo, y2, x + (-2 if side == "left" else 2), y2, LW_THIN)
        self.line(x, y1, x, y2, LW_THIN)
        self._arrow_v(x, y1, -1 if y1 > y2 else +1)
        self._arrow_v(x, y2, +1 if y1 > y2 else -1)
        tx = x - 2.2 if side == "left" else x + 2.2
        self.text(tx, (y1 + y2) / 2, text, size, "center",
                  angle=math.pi / 2, valign="middle")

    def leader(self, x1, y1, x2, y2, text=None, size=S_DIM, dot=True, shelf=0.0, side="right"):
        self.line(x1, y1, x2, y2, LW_THIN)
        if dot:
            self.circle(x1, y1, 0.5, lw=0.0, fill="#000000")
        if text is not None:
            if shelf:
                sx = -shelf if side == "left" else shelf
                self.line(x2, y2, x2 + sx, y2, LW_THIN)
                self.text(x2 + sx + (0.8 if side == "right" else -0.8), y2 - 0.4, text, size,
                          "left" if side == "right" else "right", valign="bottom")
            else:
                self.text(x2 + (0.8 if side == "right" else -0.8), y2 - 0.4, text, size,
                          "left" if side == "right" else "right", valign="bottom")

    # ---------- таблица ----------
    def table(self, x, y, widths, rows, row_h, size=2.5, header_rows=1, header_fill="#EEEEEE",
              aligns=None, bold_header=True, lw=0.25):
        total_w = sum(widths)
        total_h = row_h * len(rows)
        for ri, row in enumerate(rows):
            ry = y + ri * row_h
            if ri < header_rows and header_fill:
                self.rect(x, ry, total_w, row_h, lw=0.0, fill=header_fill)
            cx = x
            for ci, cell in enumerate(row):
                cw = widths[ci]
                al = (aligns[ci] if aligns else "left")
                bold = bold_header and ri < header_rows
                pad = 1.2
                if cell:
                    tx = cx + pad if al == "left" else (cx + cw / 2 if al == "center" else cx + cw - pad)
                    self.text(tx, ry + row_h / 2, cell, size, al, bold=bold, valign="middle")
                cx += cw
        # сетка
        for ri in range(len(rows) + 1):
            self.line(x, y + ri * row_h, x + total_w, y + ri * row_h, lw)
        cx = x
        for cw in widths:
            self.line(cx, y, cx, y + total_h, lw)
            cx += cw
        self.line(x + total_w, y, x + total_w, y + total_h, lw)

    # ---------- штриховка ----------
    def hatch(self, x, y, w, h, step=2.0, angle=45, lw=0.12):
        dx = math.cos(math.radians(angle))
        dy = -math.sin(math.radians(angle))
        span = w + h
        n = int(span / step) + 2
        for i in range(-n, n):
            ox = x + i * step
            seg = clip_line(x, y, w, h, ox, y + h, ox + dx * span, y + h + dy * span)
            if seg:
                self.line(*seg, lw=lw)

    # ---------- текст блоком с переносами ----------
    def notes(self, x, y, items, size=2.5, width=100, leading=None, numbered=True):
        leading = leading or size * 1.7
        cy = y
        for i, item in enumerate(items):
            prefix = f"{i + 1}. " if numbered else ""
            line = prefix + item
            est = text_width_mm(line, size)
            lines = max(1, int(math.ceil(est / max(width - 1.0, 5.0))))
            self.text(x, cy, line, size, "left", width=width, lines=lines)
            cy += leading + (lines - 1) * size * 1.55
        return cy

    # ---------- основная надпись (ГОСТ 2.104, форма 1) ----------
    def title_block(self, designation, title, material, mass, scale, sheet, sheets=4,
                    org="Изготовление по заказу", litera="О1", format_="А3", extra_title="",
                    subtitle=""):
        x0, y0, w, h = 230.0, 237.0, 185.0, 55.0
        self.rect(x0, y0, w, h, lw=0.7)

        # левая группа: 5 колонок по 65 мм всего
        col = [7, 10, 23, 15, 10]
        lx = [x0]
        for c in col:
            lx.append(lx[-1] + c)
        self.line(lx[-1], y0, lx[-1], y0 + h, lw=0.5)
        self.line(x0, y0 + 5, lx[-1], y0 + 5, lw=0.35)
        # первая вертикаль (Изм./Лист) — только в шапке: ниже графы «Разраб.», «Пров.» идут во всю ширину
        self.line(lx[1], y0, lx[1], y0 + 5, lw=0.25)
        for i in range(2, 5):
            self.line(lx[i], y0 + 5, lx[i], y0 + h, lw=0.25)
        for r in range(1, 5):
            self.line(x0, y0 + 5 + r * 10, lx[-1], y0 + 5 + r * 10, lw=0.25)

        caps = ["Изм.", "Лист", "№ докум.", "Подп.", "Дата"]
        for i, c in enumerate(caps):
            self.text((lx[i] + lx[i + 1]) / 2, y0 + 2.6, c, 2.0, "center", valign="middle")

        roles = ["Разраб.", "Пров.", "Т.контр.", "Н.контр.", "Утв."]
        for i, r in enumerate(roles):
            self.text(lx[0] + 1.0, y0 + 5 + i * 10 + 5, r, 2.2, "left", valign="middle")

        # правая часть 120 мм: наименование 70 + литера/масса/масштаб 50
        xr = lx[-1]
        self.line(xr, y0 + 15, x0 + w, y0 + 15, lw=0.35)
        self.line(xr, y0 + 30, x0 + w, y0 + 30, lw=0.3)
        self.line(xr, y0 + 45, x0 + w, y0 + 45, lw=0.3)
        self.line(xr + 70, y0 + 15, xr + 70, y0 + 45, lw=0.3)
        self.line(xr + 80, y0 + 15, xr + 80, y0 + 30, lw=0.25)
        self.line(xr + 100, y0 + 15, xr + 100, y0 + 30, lw=0.25)
        self.line(xr + 95, y0 + 30, xr + 95, y0 + 45, lw=0.25)
        self.line(xr + 100, y0 + 45, xr + 100, y0 + h, lw=0.25)

        # графа 2 — обозначение документа
        self.text(xr + 60, y0 + 7.6, designation, 5.0, "center", bold=True, valign="middle")

        # графа 1 — наименование
        self.text(xr + 2, y0 + 16.6, title, 3.4, "left", valign="top", width=66)
        if extra_title:
            self.text(xr + 2, y0 + 21.6, extra_title, 2.6, "left", valign="top", width=66)
        if subtitle:
            self.text(xr + 2, y0 + 17.6, subtitle, 2.6, "left", valign="top", width=66)

        self.text(xr + 75, y0 + 16.4, "Лит.", 1.8, "center", valign="top")
        self.text(xr + 90, y0 + 16.4, "Масса", 1.8, "center", valign="top")
        self.text(xr + 110, y0 + 16.4, "Масштаб", 1.8, "center", valign="top")
        self.text(xr + 75, y0 + 26.6, litera, 4.0, "center", bold=True, valign="middle")
        self.text(xr + 90, y0 + 26.6, mass, 2.8, "center", valign="middle")
        self.text(xr + 110, y0 + 26.6, scale, 4.0, "center", bold=True, valign="middle")

        self.text(xr + 82.5, y0 + 31.4, "Лист", 1.8, "center", valign="top")
        self.text(xr + 107.5, y0 + 31.4, "Листов", 1.8, "center", valign="top")
        self.text(xr + 82.5, y0 + 41.6, str(sheet), 4.2, "center", bold=True, valign="middle")
        self.text(xr + 107.5, y0 + 41.6, str(sheets), 4.2, "center", bold=True, valign="middle")

        self.text(xr + 2, y0 + 33.2, "Материал — по спецификации, лист 3", 1.9, "left", valign="top", width=66)
        self.text(xr + 2, y0 + 46.6, org, 2.2, "left", valign="top", width=66)
        self.text(xr + 110, y0 + 47.4, f"Формат {format_}", 2.2, "center", valign="middle")
