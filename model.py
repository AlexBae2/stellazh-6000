"""Параметрическая модель стеллажа 6000×700×1800 (все размеры в мм).

Один источник цифр: 3D-модель, листы Visio, спецификация и масса считаются отсюда.
Геометрия принята по исходному заданию и уточнена до технологичной конструкции.
"""
from __future__ import annotations

P = {
    "L": 6000.0,          # длина
    "D": 700.0,           # глубина
    "H": 1800.0,          # высота
    "modules": 3,         # транспортных секций по 2000
    "cells": 4,           # ячеек в секции по длине
    "rows": 2,            # ряды по высоте
    "pitch": 500.0,       # шаг ячеек
    "rowH": 900.0,        # шаг рядов
    "a": 45.0,            # полка уголка
    "t": 4.0,             # толщина уголка
    "sheet": 1.5,         # лист, мм
    "doorGap": 3.0,       # зазор в паре дверей
    "edgeGap": 1.5,       # зазор двери до стойки/пола
    "return": 20.0,       # отгиб кромки двери
    "hingesPerDoor": 3,
    "rho": 7850.0,        # кг/м³
    "angleKgM": 2.73,     # уголок 45×45×4, ГОСТ 8509-93
    "modulesMassNote": "",
}

P["modW"] = P["L"] / P["modules"]           # 2000
P["cols"] = int(P["modules"] * P["cells"])  # 12
P["doorW"] = P["pitch"] - P["doorGap"]      # 497
P["doorH"] = P["rowH"] - P["doorGap"]       # 897
P["sheetKgM2"] = P["sheet"] * P["rho"] / 1000.0
P["railLen"] = P["modW"] - 2 * P["a"]       # 1910
P["tieLen"] = P["D"] - 2 * P["a"]           # 610


def upright_axes(module: int = 0):
    """Оси стоек внутри секции (локально по X)."""
    a = P["a"]
    xs = [a / 2]
    for k in range(1, P["cells"]):
        xs.append(k * P["pitch"])
    xs.append(P["modW"] - a / 2)
    return xs


def doors():
    out = []
    for c in range(P["cols"]):
        for r in range(P["rows"]):
            m = c // P["cells"]
            local = c % P["cells"]
            x0 = c * P["pitch"] + P["doorGap"] / 2
            out.append({
                "id": f"Д{'Н' if r == 0 else 'В'}{c + 1:02d}",
                "col": c, "row": r, "module": m,
                "x0": x0, "x1": x0 + P["doorW"],
                "z0": r * P["rowH"] + P["doorGap"] / 2,
                "z1": r * P["rowH"] + P["doorGap"] / 2 + P["doorH"],
                "hingeLeft": local % 2 == 0,
            })
    return out


def cell_light():
    """Свет ячейки: крайние и средние колонки отличаются из-за стоек в шаге."""
    a = P["a"]
    return {"edge": P["pitch"] - a - a / 2, "middle": P["pitch"] - a, "height": P["rowH"] - a}


def cut_list():
    per = {
        "uprights": (5, P["H"]),        # стоек в секции
        "rails": (6, P["railLen"]),     # 3 уровня × 2 (перед/зад)
        "ties": (15, P["tieLen"]),      # 5 осей × 3 уровня
    }
    n = int(P["modules"])
    ang = [
        {"pos": "1", "name": "Стойка", "size": "L45×45×4", "qty": per["uprights"][0] * n,
         "len": per["uprights"][1], "note": "L = 1800, 10 шт. на секцию"},
        {"pos": "2", "name": "Перекладина продольная", "size": "L45×45×4", "qty": per["rails"][0] * n,
         "len": per["rails"][1], "note": "L = 1910, 6 шт. на секцию"},
        {"pos": "3", "name": "Связь по глубине", "size": "L45×45×4", "qty": per["ties"][0] * n,
         "len": per["ties"][1], "note": "L = 610, 15 шт. на секцию"},
    ]
    ang_m = sum(x["qty"] * x["len"] for x in ang) / 1000.0
    ang_kg = ang_m * P["angleKgM"]

    sh = [
        {"pos": "5", "name": "Задняя стенка", "size": "2000×1800", "qty": n,
         "note": "лист 1,5, прихватки к каркасу"},
        {"pos": "6", "name": "Крышка", "size": "2000×700", "qty": n, "note": "лист 1,5, отгиб 20 по фасаду"},
        {"pos": "7", "name": "Днище", "size": "2000×700", "qty": n, "note": "лист 1,5, отгиб 20 по фасаду"},
        {"pos": "8", "name": "Перекрытие между рядами", "size": "2000×700", "qty": n,
         "note": "лист 1,5, усилить рёбрами при нагрузке > 40 кг/м²"},
        {"pos": "4", "name": "Дверь", "size": "497×897", "qty": P["cols"] * P["rows"],
         "note": "лист 1,5, отгиб 20 по 4 сторонам"},
    ]
    for s in sh:
        w, h = [float(v) for v in s["size"].split("×")]
        s["area"] = w * h / 1e6
    sheet_area = sum(s["area"] * s["qty"] for s in sh)
    sheet_kg = sheet_area * P["sheetKgM2"]

    hw = [
        {"pos": "9", "name": "Петля накладная усиленная 80 мм", "qty": P["cols"] * P["rows"] * P["hingesPerDoor"]},
        {"pos": "10", "name": "Замок врезной с ключами (2 ключа)", "qty": P["cols"] * P["rows"]},
        {"pos": "11", "name": "Ручка-скоба на пару дверей", "qty": P["cols"] * P["rows"] // 2},
        {"pos": "12", "name": "Болт М8×30 ГОСТ 7798-70 + гайка + 2 шайбы", "qty": 8},
        {"pos": "13", "name": "Опора регулируемая М10, ±10 мм", "qty": 4 * n},
        {"pos": "14", "name": "Анкер клиновой 10×80 для крепления к стене", "qty": 4},
    ]
    hw_kg = 72 * 0.06 + 24 * 0.35 + 12 * 0.05 + 8 * 0.03 + 12 * 0.12 + 4 * 0.08

    total_kg = ang_kg + sheet_kg + hw_kg
    return {
        "angles": ang, "angle_m": ang_m, "angle_kg": ang_kg,
        "sheets": sh, "sheet_area": sheet_area, "sheet_kg": sheet_kg,
        "hw": hw, "hw_kg": hw_kg, "total_kg": total_kg,
    }


def fmt(v: float, nd: int = 0) -> str:
    s = f"{v:,.{nd}f}".replace(",", " ").replace(".", ",")
    return s


if __name__ == "__main__":
    c = cut_list()
    print(f"уголок {c['angle_m']:.1f} м = {c['angle_kg']:.0f} кг")
    print(f"лист {c['sheet_area']:.1f} м² = {c['sheet_kg']:.0f} кг")
    print(f"фурнитура {c['hw_kg']:.0f} кг")
    print(f"итого ≈ {c['total_kg']:.0f} кг, на секцию ≈ {c['total_kg'] / P['modules']:.0f} кг")
    print("свет ячейки:", cell_light())
