"""Контроль качества чертежа: наложения подписей и пересечения текст/линии."""
from __future__ import annotations

import sys

import build


def inter(a, b, pad=0.0):
    x0, y0 = max(a[0], b[0]) - pad, max(a[1], b[1]) - pad
    x1, y1 = min(a[2], b[2]) + pad, min(a[3], b[3]) + pad
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def seg_hits_box(p1, p2, box):
    """Пересекает ли отрезок внутренность прямоугольника (сжатого на 0.25 мм)."""
    x0, y0, x1, y1 = box[0] + 0.25, box[1] + 0.25, box[2] - 0.25, box[3] - 0.25
    if x1 <= x0 or y1 <= y0:
        return False
    # Лян-Барски
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, p1[0] - x0), (dx, x1 - p1[0]), (-dy, p1[1] - y0), (dy, y1 - p1[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def rot_box(box, angle):
    if abs(angle) < 1e-6:
        return box
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    hw, hh = (box[2] - box[0]) / 2, (box[3] - box[1]) / 2
    if abs(abs(angle) - 1.5707963) < 0.01:   # ±90°: меняем полуоси
        hw, hh = hh, hw
    return (cx - hw, cy - hh, cx + hw, cy + hh)


def check(page):
    texts = [(rot_box(it[1], it[4] if len(it) > 4 else 0.0), it[2], it[3])
             for it in page.items if it[0] == "text" and it[2].strip()]
    lines = [it[1] for it in page.items if it[0] == "line" and it[2] > 0]
    problems = []

    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i][0], texts[j][0]
            area = inter(a, b)
            if area > 0.2:
                problems.append(("text-text", area, texts[i][1], texts[j][1], a, b))
            elif area == 0:
                dx = max(0.0, max(a[0] - b[2], b[0] - a[2]))
                dy = max(0.0, max(a[1] - b[3], b[1] - a[3]))
                gap = (dx * dx + dy * dy) ** 0.5
                if 0 < gap < 0.9:
                    problems.append(("text-gap", gap, texts[i][1], texts[j][1], a, b))

    # текст и линии: только «жирные» линии чертежа, тонкие выноски тоже важны
    for box, s, size in texts:
        hits = 0
        for seg in lines:
            for k in range(len(seg) - 1):
                if seg_hits_box(seg[k], seg[k + 1], box):
                    hits += 1
                    break
            if hits >= 1:
                break
        if hits:
            problems.append(("text-line", 0, s, "", box, None))

    for box, s_, size in texts:
        if box[0] < 20.2 or box[2] > 414.8 or box[1] < 5.2 or box[3] > 291.8:
            problems.append(("outside", 0, s_, "", box, None))

    return problems


def main():
    builders = {"1": build.sheet1, "2": build.sheet2, "3": build.sheet3, "4": build.sheet4}
    keys = sys.argv[1:] or ["1", "2", "3", "4"]
    total = 0
    for k in keys:
        page = builders[k]()
        probs = check(page)
        total += len(probs)
        print(f"\n=== лист {k} ({page.name}): проблем {len(probs)}")
        tt = [p for p in probs if p[0] == "text-text"]
        tl = [p for p in probs if p[0] == "text-line"]
        tg = [p for p in probs if p[0] == "text-gap"]
        ou = [p for p in probs if p[0] == "outside"]
        print(f"    текст-текст: {len(tt)}, текст-линия: {len(tl)}, зазор<0.9: {len(tg)}, за рамкой: {len(ou)}")
        for p in sorted(tt, key=lambda x: -x[1])[:15]:
            print(f"    [TT {p[1]:5.1f} мм²] {p[2]!r}  ×  {p[3]!r}")
        for p in sorted(tg, key=lambda x: x[1])[:8]:
            print(f"    [GAP {p[1]:4.2f}] {p[2]!r}  ×  {p[3]!r}")
        for p in ou[:8]:
            print(f"    [OUT] {p[2]!r} box={tuple(round(v,1) for v in p[4])}")
        for p in tl[:12]:
            print(f"    [TL] {p[2]!r} box={tuple(round(v,1) for v in p[4])}")
            for seg in [it[1] for it in page.items if it[0] == "line" and it[2] > 0]:
                for k in range(len(seg) - 1):
                    if seg_hits_box(seg[k], seg[k + 1], p[4]):
                        print(f"         линия {tuple(round(v,1) for v in seg[k])} -> {tuple(round(v,1) for v in seg[k+1])}")
                        break
    print("\nвсего:", total)


if __name__ == "__main__":
    main()
