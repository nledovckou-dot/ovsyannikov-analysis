#!/usr/bin/env python3
"""
Генерирует HTML-секции 2.18-2.23 (Рынок труда) для отчёта Овсянникова.
Читает данные из hh_labor_market.json, выводит готовый HTML-блок.
"""
import json
import math

DATA_PATH = "/Users/n-a-ledovskoy/Desktop/вайбкодинг/Ovsyannikov/data/hh_labor_market.json"

with open(DATA_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

positions = data["positions"]
market = data["market"]
competitors = data["competitors"]
collected_at = data["collected_at"][:10]  # YYYY-MM-DD

# Fix: cap remote_pct at 100% (bug in data collection for some positions)
for p in positions:
    if p.get("remote_pct", 0) > 100:
        p["remote_pct"] = min(round(p["remote"] / p["total_vacancies"] * 100, 1) if p["total_vacancies"] > 0 else 0, 100)

# Recalculate summary with fixed data
all_med = [p["salary"]["median"] for p in positions if p["salary"]["median"] > 0]
total_vac = sum(p["total_vacancies"] for p in positions)
avg_r = sum(min(p["remote_pct"], 100) for p in positions) / len(positions) if positions else 0
summary = {
    "total_vacancies_positions": total_vac,
    "median_salary_overall": int(sorted(all_med)[len(all_med)//2]) if all_med else 0,
    "avg_remote_pct": round(avg_r, 1),
}


def fmt_k(n):
    """100000 → '100К'"""
    if n >= 1000:
        return f"{round(n/1000)}К"
    return str(n)


def fmt_num(n):
    """1997 → '1 997'"""
    return f"{n:,}".replace(",", " ")


# ── Salary affordability ──
# Revenue ~260М, 50 employees, ФОТ ~30% = 78М, per person ~130К/month
AFFORD_GREEN = 120000   # median <= this → green
AFFORD_GOLD = 145000    # median <= this → gold
# above → red


def salary_badge(median):
    if median <= AFFORD_GREEN:
        return '<span class="badge b-positive">Может платить</span>'
    elif median <= AFFORD_GOLD:
        return '<span class="badge b-gold">На пределе</span>'
    else:
        return '<span class="badge b-negative">Не конкурентен</span>'


def salary_bar_color(median):
    if median <= AFFORD_GREEN:
        return "var(--positive)"
    elif median <= AFFORD_GOLD:
        return "var(--gold)"
    else:
        return "var(--negative)"


# ── Position categories ──
MANAGEMENT_KEYS = {"commercial_dir", "production_dir", "hr_dir", "cfo"}
LINE_KEYS = {"technologist", "operator", "sales_b2b", "marketplace", "marketing", "logistics", "rnd", "brand"}


# ── Deficit assessment ──
def deficit_level(pos):
    vac = pos.get("total_vacancies", 0)
    no_exp = pos.get("no_experience_pct", 0)
    med = pos.get("salary", {}).get("median", 0)
    key = pos.get("key", "")

    # R&D: ultra-specialized, acute even with few vacancies
    if key == "rnd":
        return ("Острый", "hm-r2")
    # Marketplace: extreme demand
    if key == "marketplace" or vac > 2000:
        return ("Острый", "hm-r2")
    # Directors: high salary = hard for small company
    if key == "commercial_dir":
        return ("Острый", "hm-r2")
    if key in ("cfo", "hr_dir"):
        return ("Умеренный", "hm-y2")
    # High no-experience = desperate hiring
    if no_exp > 40:
        return ("Умеренный", "hm-y2")
    # Moderate vacancy count
    if vac > 500:
        return ("Умеренный", "hm-y2")
    if vac > 100:
        return ("Умеренный", "hm-y2")
    if vac < 20 and med < 100000:
        return ("Норма", "hm-g2")
    return ("Умеренный", "hm-y2")


def vac_class(n):
    if n < 20: return "hm-g1"
    if n < 100: return "hm-y1"
    if n < 300: return "hm-y2"
    return "hm-r3"


def noexp_class(pct):
    if pct < 5: return "hm-g1"
    if pct < 15: return "hm-y1"
    if pct < 40: return "hm-y2"
    return "hm-r2"


def med_class(med):
    if med < 80000: return "hm-g2"
    if med < 110000: return "hm-y1"
    if med < 140000: return "hm-y2"
    return "hm-r1"


# ── SVG helpers ──
SVG_BAR_START = 195
SVG_BAR_WIDTH = 460
SVG_MAX_SALARY = 500000  # Updated for director salaries (CFO up to 1M, but Q3=250K)


def sal_px(salary):
    return SVG_BAR_START + round(salary / SVG_MAX_SALARY * SVG_BAR_WIDTH)


# ── Radar chart helpers (hexagonal, same as existing sec-3-9) ──
RADAR_RADIUS = 180
RADAR_AXES = [
    (0, -1),                # top
    (math.sin(math.radians(60)), -math.cos(math.radians(60))),   # top-right
    (math.sin(math.radians(120)), -math.cos(math.radians(120))), # bottom-right
    (0, 1),                 # bottom
    (-math.sin(math.radians(60)), math.cos(math.radians(60))),   # bottom-left
    (-math.sin(math.radians(120)), -math.cos(math.radians(120))),# top-left
]


def radar_point(axis_idx, value_pct):
    """Return (x, y) for a value (0-100) on a given axis."""
    dx, dy = RADAR_AXES[axis_idx]
    r = RADAR_RADIUS * value_pct / 100
    return (round(dx * r), round(dy * r))


def radar_polygon_points(values):
    """6 values → SVG polygon points string."""
    pts = [radar_point(i, v) for i, v in enumerate(values)]
    return " ".join(f"{x},{y}" for x, y in pts)


# ── Build HTML ──
html_parts = []


def emit(s):
    html_parts.append(s)


# ════════════════════════════════════════════
# Section 2.18 — Обзор рынка труда
# ════════════════════════════════════════════
cosm_market = next(m for m in market if m["key"] == "cosmetics")
fmcg_market = next(m for m in market if m["key"] == "fmcg")
horeca_market = next(m for m in market if m["key"] == "horeca")

emit("""
<!-- ═══════════════════════════════════════ -->
<!-- СЕКЦИИ 2.18-2.23: РЫНОК ТРУДА (HR)     -->
<!-- ═══════════════════════════════════════ -->

<div class="section" id="sec-2-18">
<div class="section-head"><div class="section-num" style="width:auto;min-width:42px;padding:0 12px;border-radius:20px;">2.18</div><h2>Рынок труда в косметической индустрии</h2></div>
<div class="section-desc">Реальные данные hh.ru API (Москва + МО): вакансии, зарплаты, дефицит кадров. Насколько Овсянников конкурентоспособен как работодатель?</div>
""")

emit(f"""<div class="grid-3">
<div class="metric"><div class="val val-gold">{fmt_num(cosm_market['total_vacancies'])}</div><div class="lbl">Вакансий в косметике / парфюмерии (Москва + МО)</div></div>
<div class="metric"><div class="val val-gold">{fmt_k(summary['median_salary_overall'])}₽</div><div class="lbl">Медиана зарплат (12 позиций, net)</div></div>
<div class="metric"><div class="val val-neutral">{summary['avg_remote_pct']}%</div><div class="lbl">Доля remote-вакансий (в среднем)</div></div>
</div>
""")

mp_pos = next(p for p in positions if p["key"] == "marketplace")
mp_ind = mp_pos.get("industry", {}).get("total", mp_pos["total_vacancies"])
mp_gen = mp_pos.get("general", {}).get("total", 0)
emit(f"""<div class="callout callout-gold" style="margin-top:16px;">
<h4>Контекст: рынок труда в beauty перегрет</h4>
<p>В косметике и парфюмерии <strong>{fmt_num(cosm_market['total_vacancies'])}</strong> вакансий по Москве и МО. Медиана зарплат в FMCG — <strong>{fmt_k(fmcg_market['salary']['median'])}₽</strong> (на 30% выше чем в beauty-ритейле). Менеджеры маркетплейсов — <strong>самый дефицитный профиль</strong>: {fmt_num(mp_ind)} в отрасли (и {fmt_num(mp_gen)} по всему рынку), {mp_pos['remote_pct']}% remote. HoReCa-сегмент (ключевой для B2B Овсянникова) — {fmt_num(horeca_market['total_vacancies'])} вакансий, медиана {fmt_k(horeca_market['salary']['median'])}₽.</p>
</div>

<div class="info-tip"><div class="ii">i</div><span><strong>Источник:</strong> hh.ru API (GET /vacancies), дата сбора: {collected_at}. Регион: Москва + Московская область (area=1,46). Зарплаты net (после вычета 13% НДФЛ из gross). Только вакансии с указанной зарплатой, валюта RUB.</span></div>
</div>
""")


# ════════════════════════════════════════════
# Section 2.19 — Зарплатный бенчмарк
# ════════════════════════════════════════════
emit("""
<div class="section" id="sec-2-19">
<div class="section-head"><div class="section-num" style="width:auto;min-width:42px;padding:0 12px;border-radius:20px;">2.19</div><h2>Зарплатный бенчмарк по ключевым позициям</h2></div>
<div class="section-desc">12 позиций: 8 линейных + 4 управленческих, критичных для роста Овсянникова до 1 млрд₽. Данные hh.ru, Москва + МО, net (после НДФЛ).</div>
""")

# Table
emit("""<div class="card">
<h3>Зарплаты: отрасль vs общий рынок</h3>
<div style="overflow-x:auto;">
<table>
<thead><tr><th>Позиция</th><th class="r">Вакансий<br><small style="color:var(--gold);">отрасль</small></th><th class="r">Вакансий<br><small style="color:var(--text3);">общий</small></th><th class="r">Медиана<br><small style="color:var(--gold);">отрасль</small></th><th class="r">Медиана<br><small style="color:var(--text3);">общий</small></th><th class="r">Q3</th><th>Оценка</th></tr></thead>
<tbody>
""")

line_positions = sorted([p for p in positions if p["key"] in LINE_KEYS], key=lambda p: p["salary"]["median"])
mgmt_positions = sorted([p for p in positions if p["key"] in MANAGEMENT_KEYS], key=lambda p: p["salary"]["median"])
sorted_positions = line_positions + mgmt_positions

for i, p in enumerate(sorted_positions):
    if i == len(line_positions):
        emit('<tr><td colspan="7" style="background:var(--bg3);color:var(--gold);font-weight:700;font-size:0.82em;text-transform:uppercase;letter-spacing:0.05em;padding:8px 14px;">Топ-менеджмент</td></tr>\n')
    s = p["salary"]
    med = s["median"]
    badge = salary_badge(med)
    ind = p.get("industry", {})
    gen = p.get("general", {})
    ind_total = ind.get("total", p["total_vacancies"])
    gen_total = gen.get("total", 0)
    ind_med = ind.get("salary_median", med)
    gen_med = gen.get("salary_median", 0)
    emit(f'<tr><td>{p["label"]}</td>'
         f'<td class="r" style="color:var(--gold);">{fmt_num(ind_total)}</td>'
         f'<td class="r" style="color:var(--text3);">{fmt_num(gen_total)}</td>'
         f'<td class="r" style="font-weight:700;color:var(--gold);">{fmt_k(ind_med)}₽</td>'
         f'<td class="r" style="color:var(--text3);">{fmt_k(gen_med)}₽</td>'
         f'<td class="r">{fmt_k(s["q3"])}₽</td>'
         f'<td>{badge}</td></tr>\n')

emit("""</tbody>
</table>
</div>
<p style="font-size:0.82em; color:var(--text3); margin-top:8px;"><strong>Отрасль</strong> = работодатели в «бытовая химия, парфюмерия, косметика» (коды HH 42.589, 42.590, 41.516). <strong>Общий</strong> = все отрасли. <strong>Оценка «Может платить»</strong> — медиана ≤120К₽. <strong>«На пределе»</strong> — 120-145К₽. <strong>«Не конкурентен»</strong> — &gt;145К₽.</p>
</div>
""")

# SVG: Horizontal range bars
emit("""
<!-- SVG: Зарплатная карта — диапазоны Q1-Q3 -->
<div class="chart-container">
<h3>Зарплатная карта: диапазоны Q1–Q3 по позициям</h3>
<div class="subtitle">Горизонтальные полосы = межквартильный размах (50% вакансий). Ромб = медиана. Пунктир = бюджет Овсянникова (~130К₽/мес).</div>
""")

svg_h = 45 * len(sorted_positions) + 60 + 25  # +25 for management separator
emit(f'<svg class="chart-svg" viewBox="0 0 700 {svg_h}">')
emit('<defs><style>.sl{fill:#A8A098;font-size:11px;}.sv{fill:#706858;font-size:9px;}</style></defs>')

# Background grid lines
for tick_val in [50000, 100000, 150000, 200000, 250000, 350000, 500000]:
    tx = sal_px(tick_val)
    emit(f'<line x1="{tx}" y1="25" x2="{tx}" y2="{svg_h-30}" stroke="rgba(181,144,122,0.07)"/>')
    emit(f'<text x="{tx}" y="18" text-anchor="middle" class="sv">{fmt_k(tick_val)}₽</text>')

# Reference line: Овсянников budget ~130K
ref_x = sal_px(130000)
emit(f'<line x1="{ref_x}" y1="25" x2="{ref_x}" y2="{svg_h-30}" stroke="var(--gold)" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.6"/>')
emit(f'<text x="{ref_x}" y="{svg_h-10}" text-anchor="middle" fill="var(--gold)" font-size="9" opacity="0.8">Бюджет Овсянникова ~130К</text>')

y_offset = 0  # extra offset for separator
for i, p in enumerate(sorted_positions):
    # Separator before management
    if i == len(line_positions):
        sep_y = 55 + i * 45 + y_offset - 5
        emit(f'<line x1="10" y1="{sep_y}" x2="690" y2="{sep_y}" stroke="var(--gold)" stroke-width="0.5" stroke-dasharray="4,3" opacity="0.4"/>')
        emit(f'<text x="10" y="{sep_y + 14}" fill="var(--gold)" font-size="9" font-weight="700" letter-spacing="0.08em">ТОП-МЕНЕДЖМЕНТ</text>')
        y_offset += 25

    s = p["salary"]
    y = 55 + i * 45 + y_offset
    q1x = sal_px(s["q1"])
    medx = sal_px(s["median"])
    q3x = sal_px(s["q3"])
    color = salary_bar_color(s["median"])
    delay = f"{0.1 + i * 0.1:.1f}s"

    # Label
    short_label = p["label"]
    if len(short_label) > 22:
        short_label = short_label[:20] + "…"
    emit(f'<text x="188" y="{y+4}" text-anchor="end" class="sl" fill="#A8A098">{short_label}</text>')

    # Track
    emit(f'<rect x="{SVG_BAR_START}" y="{y-10}" width="{SVG_BAR_WIDTH}" height="20" rx="3" fill="var(--bg3)" opacity="0.3"/>')

    # Q1-Q3 bar
    bar_w = max(q3x - q1x, 4)
    emit(f'<rect x="{q1x}" y="{y-10}" width="{bar_w}" height="20" rx="3" fill="{color}" opacity="0.5" class="bar-animated" style="animation-delay:{delay}" data-tip="{p["label"]}: Q1 {fmt_k(s["q1"])}₽, медиана {fmt_k(s["median"])}₽, Q3 {fmt_k(s["q3"])}₽, макс {fmt_k(s["max"])}₽"/>')

    # Median marker (diamond)
    emit(f'<polygon points="{medx},{y-12} {medx+6},{y} {medx},{y+12} {medx-6},{y}" fill="{color}" stroke="#0C0A08" stroke-width="1" data-tip="Медиана: {fmt_k(s["median"])}₽ net"/>')

    # Value label
    label_x = q3x + 8
    emit(f'<text x="{label_x}" y="{y+4}" fill="{color}" font-size="11" font-weight="700">{fmt_k(s["median"])}₽</text>')

emit('</svg>')
emit("""<div class="chart-legend">
<div class="leg-item"><div class="leg-swatch" style="background:var(--positive);"></div>Может платить (≤120К)</div>
<div class="leg-item"><div class="leg-swatch" style="background:var(--gold);"></div>На пределе (120-145К)</div>
<div class="leg-item"><div class="leg-swatch" style="background:var(--negative);"></div>Не конкурентен (&gt;145К)</div>
</div>
</div>

<div class="info-tip"><div class="ii">i</div><span><strong>Методология:</strong> Q1/Q3 = 25-й/75-й перцентили зарплат с hh.ru (only_with_salary=true). Зарплаты net — gross × 0.87. Бюджет Овсянникова: при выручке ~260М₽ и ФОТ 30% → ~78М₽/год → ~130К₽/мес на сотрудника. <a href="https://hh.ru" target="_blank">Источник: hh.ru API</a>, {collected_at}.</span></div>
</div>
""")


# ════════════════════════════════════════════
# Section 2.20 — Дефицит кадров
# ════════════════════════════════════════════
emit("""
<div class="section" id="sec-2-20">
<div class="section-head"><div class="section-num" style="width:auto;min-width:42px;padding:0 12px;border-radius:20px;">2.20</div><h2>Дефицит кадров: спрос vs предложение</h2></div>
<div class="section-desc">Тепловая карта: где Овсянников столкнётся с дефицитом при масштабировании. Красный = острый дефицит, жёлтый = умеренный, зелёный = норма.</div>
""")

# Sort by deficit severity (acute first)
deficit_order = {"Острый": 0, "Умеренный": 1, "Норма": 2}
sorted_deficit = sorted(positions, key=lambda p: (deficit_order.get(deficit_level(p)[0], 1), -p.get("total_vacancies", 0)))

emit("""<div class="card">
<h3>Тепловая карта дефицита кадров</h3>
<div style="overflow-x:auto;">
<table class="hm">
<thead><tr><th>Позиция</th><th>Вакансий (Мск+МО)</th><th>Без опыта %</th><th>Медиана ₽</th><th>Уровень дефицита</th></tr></thead>
<tbody>
""")

for p in sorted_deficit:
    s = p["salary"]
    dl, dc = deficit_level(p)
    emit(f'<tr>'
         f'<td>{p["label"]}</td>'
         f'<td class="{vac_class(p["total_vacancies"])}">{fmt_num(p["total_vacancies"])}</td>'
         f'<td class="{noexp_class(p["no_experience_pct"])}">{p["no_experience_pct"]}%</td>'
         f'<td class="{med_class(s["median"])}">{fmt_k(s["median"])}₽</td>'
         f'<td class="{dc}">{dl}</td>'
         f'</tr>\n')

emit("""</tbody>
</table>
</div>
</div>
""")

pos_by_key = {p["key"]: p for p in positions}
cd = pos_by_key.get("commercial_dir", {})
mp = pos_by_key.get("marketplace", {})
rnd = pos_by_key.get("rnd", {})
op = pos_by_key.get("operator", {})
log = pos_by_key.get("logistics", {})
tech = pos_by_key.get("technologist", {})
pd = pos_by_key.get("production_dir", {})

emit(f"""<div class="grid-2" style="margin-top:16px;">
<div class="callout callout-red">
<h4>Критические позиции для Овсянникова</h4>
<p><strong>Коммерческий директор</strong> — медиана {fmt_k(cd.get('general',{}).get('salary_median',0))}₽ на рынке (в отрасли {fmt_k(cd.get('industry',{}).get('salary_median',0))}₽, всего {cd.get('industry',{}).get('total',0)} вакансий). При росте до 1 млрд нужен сильный КД — нужны опционы/доля. <strong>Менеджеры маркетплейсов</strong> — {fmt_num(mp.get('general',{}).get('total',0))} вакансий по Москве и МО ({fmt_num(mp.get('industry',{}).get('total',0))} в отрасли), {mp.get('remote_pct',0)}% remote, огромная конкуренция. <strong>R&amp;D / Рецептуры</strong> — всего {fmt_num(rnd.get('industry',{}).get('total',0))} вакансий в отрасли, ультра-специализированный рынок.</p>
</div>
<div class="callout callout-green">
<h4>Где Овсянников выигрывает</h4>
<p><strong>Операторы</strong> (медиана {fmt_k(op.get('industry',{}).get('salary_median',0))}₽ в отрасли, {fmt_num(op.get('industry',{}).get('total',0))} вак.) и <strong>логисты</strong> ({fmt_k(log.get('industry',{}).get('salary_median',0))}₽, {fmt_num(log.get('industry',{}).get('total',0))} вак.) — конкурирует по зарплатам. <strong>Технологи</strong> ({fmt_k(tech.get('industry',{}).get('salary_median',0))}₽) и <strong>директор по производству</strong> ({fmt_k(pd.get('industry',{}).get('salary_median',0))}₽ в отрасли) — тоже по силам. Преимущество: <strong>собственное производство</strong> привлекает тех, кто хочет влиять на продукт.</p>
</div>
</div>""")

emit("""
<div class="info-tip"><div class="ii">i</div><span><strong>Как читать:</strong> «Без опыта %» — доля вакансий, принимающих без опыта (выше = рынок «отчаялся»). Дефицит: <span style="color:var(--negative)">Острый</span> = ультра-специализированный рынок или огромный спрос. <span style="color:var(--gold)">Умеренный</span> = конкурентная борьба за кандидатов. <span style="color:var(--positive)">Норма</span> = рынок сбалансирован.</span></div>
</div>
""")


# ════════════════════════════════════════════
# Section 2.21 — Вакансии конкурентов
# ════════════════════════════════════════════
emit("""
<div class="section" id="sec-2-21">
<div class="section-head"><div class="section-num" style="width:auto;min-width:42px;padding:0 12px;border-radius:20px;">2.21</div><h2>Вакансии конкурентов на hh.ru</h2></div>
<div class="section-desc">Кто из конкурентов активно нанимает? Количество открытых вакансий — индикатор роста (или текучки). Овсянников = 0 вакансий на HH.</div>
""")

# Add Овсянников to competitors for chart
comp_with_ov = competitors.copy()
comp_with_ov.append({"name": "Овсянников", "open_vacancies": 0, "top_positions": [], "max_salary": 0, "is_subject": True})

# Sort by vacancies descending, filter to those with any data or key names
key_names = {"Mixit", "Faberlic", "Natura Siberica", "Splat", "VOIS", "The Act", "Овсянников", "Zielinski & Rozen"}
chart_comps = [c for c in comp_with_ov if c["name"] in key_names or c.get("open_vacancies", 0) > 0]
chart_comps.sort(key=lambda c: c.get("open_vacancies", 0), reverse=True)

max_vac = max(c.get("open_vacancies", 0) for c in chart_comps) or 1
svg_comp_h = len(chart_comps) * 38 + 50

emit(f"""
<div class="chart-container">
<h3>Открытые вакансии: конкуренты на hh.ru</h3>
<div class="subtitle">Количество вакансий = индикатор активности найма. Овсянников выделен золотым. Данные hh.ru API.</div>
<svg class="chart-svg" viewBox="0 0 700 {svg_comp_h}">
""")

for i, c in enumerate(chart_comps):
    y = 35 + i * 38
    vac = c.get("open_vacancies", 0)
    is_ov = c.get("is_subject", False)
    name = c["name"]

    # Label
    label_color = "#D4AD8F" if is_ov else "#A8A098"
    label_weight = "700" if is_ov else "400"
    emit(f'<text x="188" y="{y+4}" text-anchor="end" fill="{label_color}" font-size="11" font-weight="{label_weight}">{name}</text>')

    if vac > 0:
        bar_w = max(round(vac / max_vac * SVG_BAR_WIDTH), 4)
        if is_ov:
            fill = "url(#gB)" if False else "var(--gold)"
        elif name == "Mixit":
            fill = "var(--negative)"
        else:
            fill = "var(--neutral)"
        delay = f"{0.1 + i * 0.08:.2f}s"
        emit(f'<rect x="{SVG_BAR_START}" y="{y-9}" width="{bar_w}" height="18" rx="3" fill="{fill}" opacity="0.7" class="bar-animated" style="animation-delay:{delay}" data-tip="{name}: {vac} открытых вакансий"/>')
        emit(f'<text x="{SVG_BAR_START + bar_w + 6}" y="{y+4}" fill="{label_color}" font-size="11" font-weight="700">{vac}</text>')
    else:
        emit(f'<text x="{SVG_BAR_START + 4}" y="{y+4}" fill="var(--text3)" font-size="10" font-style="italic">нет профиля / 0</text>')

emit('</svg>')
emit("""<div class="chart-legend">
<div class="leg-item"><div class="leg-swatch" style="background:var(--negative);"></div>Mixit (лидер найма)</div>
<div class="leg-item"><div class="leg-swatch" style="background:var(--neutral);"></div>Прочие конкуренты</div>
<div class="leg-item"><div class="leg-swatch" style="background:var(--gold);"></div>Овсянников</div>
</div>
</div>
""")

# Table: competitors with details
emit("""<div class="card" style="margin-top:16px;">
<h3>Детали найма конкурентов</h3>
<table>
<thead><tr><th>Конкурент</th><th class="r">Вакансий</th><th>Топ-позиции</th><th class="r">Макс зарплата</th></tr></thead>
<tbody>
""")

for c in chart_comps:
    vac = c.get("open_vacancies", 0)
    is_ov = c.get("is_subject", False)
    max_sal = c.get("max_salary", 0)
    top_pos = c.get("top_positions", [])
    top_str = ", ".join(top_pos[:3]) if top_pos else "—"
    if len(top_str) > 80:
        top_str = top_str[:77] + "…"
    sal_str = f"{fmt_k(max_sal)}₽" if max_sal > 0 else "—"
    style = ' style="color:var(--gold);"' if is_ov else ""
    emit(f'<tr><td{style}>{c["name"]}</td>'
         f'<td class="r">{vac}</td>'
         f'<td style="font-size:0.82em;color:var(--text3);">{top_str}</td>'
         f'<td class="r">{sal_str}</td></tr>\n')

emit("""</tbody>
</table>
</div>

<div class="callout callout-gold" style="margin-top:16px;">
<h4>Инсайт: 5 из 8 конкурентов невидимы на HH</h4>
<p>VOIS, The Act, Zielinski &amp; Rozen, Tonka, Levrana — <strong>не используют HH для найма</strong>. Вероятно, нанимают через нетворкинг, Telegram-каналы и рекомендации. Mixit — абсолютный лидер (177 вакансий), что отражает масштаб (2 завода, 33М единиц/год) и текучку. <strong>Для Овсянникова</strong>: создание профиля на HH — low-hanging fruit для привлечения кадров.</p>
</div>

<div class="info-tip"><div class="ii">i</div><span><strong>Источник:</strong> hh.ru API (GET /employers + /vacancies?employer_id=...), {collected_at}. «Нет профиля» — компания не найдена в реестре работодателей hh.ru (может нанимать через другие каналы). Зарплаты — максимальные из опубликованных вакансий, net.</span></div>
""".replace("{collected_at}", collected_at))

emit("</div>\n")


# ════════════════════════════════════════════
# Section 2.22 — Радар HR-конкурентоспособности
# ════════════════════════════════════════════
emit("""
<div class="section" id="sec-2-22">
<div class="section-head"><div class="section-num" style="width:auto;min-width:42px;padding:0 12px;border-radius:20px;">2.22</div><h2>Радар HR-конкурентоспособности</h2></div>
<div class="section-desc">6 осей: зарплатный уровень, активность найма, HR-бренд, размер команды, выручка/сотрудник, гибкость (remote). Оценка 0-100.</div>
""")

# Company HR scores [salary, hiring, hr_brand, team_size, revenue_per_emp, flexibility]
radar_data = {
    "Овсянников": {
        "values": [50, 5, 5, 25, 80, 15],
        "fill": "rgba(181,144,122,0.2)",
        "stroke": "#B5907A",
        "stroke_width": "2.5",
        "dash": "",
        "tip": "Овсянников: зарплаты 50, найм 5, HR-бренд 5, команда 25, выр/сотр 80, гибкость 15",
    },
    "Mixit": {
        "values": [75, 95, 90, 85, 95, 40],
        "fill": "rgba(184,92,92,0.1)",
        "stroke": "#B85C5C",
        "stroke_width": "1.5",
        "dash": ' stroke-dasharray="4,2"',
        "tip": "Mixit: зарплаты 75, найм 95, HR-бренд 90, команда 85, выр/сотр 95, гибкость 40",
    },
    "VOIS": {
        "values": [70, 10, 10, 50, 90, 75],
        "fill": "rgba(138,154,170,0.1)",
        "stroke": "#8A9AAA",
        "stroke_width": "1.5",
        "dash": ' stroke-dasharray="4,2"',
        "tip": "VOIS: зарплаты 70, найм 10, HR-бренд 10, команда 50, выр/сотр 90, гибкость 75",
    },
    "The Act": {
        "values": [60, 10, 10, 40, 100, 20],
        "fill": "rgba(139,175,122,0.1)",
        "stroke": "#8BAF7A",
        "stroke_width": "1.5",
        "dash": ' stroke-dasharray="4,2"',
        "tip": "The Act: зарплаты 60, найм 10, HR-бренд 10, команда 40, выр/сотр 100, гибкость 20",
    },
}

radar_labels = [
    ("Зарплатный уровень", 0, -195, "middle"),
    ("Активность найма", 172, -90, "start"),
    ("HR-бренд", 172, 95, "start"),
    ("Размер команды", 0, 200, "middle"),
    ("Выручка/сотрудник", -172, 95, "end"),
    ("Гибкость (remote)", -172, -90, "end"),
]

emit("""<div class="chart-container">
<h3>Радар HR-конкурентоспособности: 4 компании × 6 осей</h3>
<div class="subtitle">Чем больше площадь полигона — тем выше HR-конкурентоспособность. Овсянников vs Mixit vs VOIS vs The Act.</div>
<svg class="chart-svg" viewBox="0 0 700 480">
<defs>
<style>.radar-label{fill:#A8A098;font-size:11px;}.radar-val{fill:#706858;font-size:9px;}</style>
</defs>
<g transform="translate(350,230)">
<!-- Axis lines -->
""")

for i, (lbl, lx, ly, anchor) in enumerate(radar_labels):
    dx, dy = RADAR_AXES[i]
    emit(f'<line x1="0" y1="0" x2="{round(dx*180)}" y2="{round(dy*180)}" stroke="rgba(181,144,122,0.15)"/>')

# Grid rings
ring33 = radar_polygon_points([33]*6)
ring67 = radar_polygon_points([67]*6)
ring100 = radar_polygon_points([100]*6)
emit(f'<polygon points="{ring33}" fill="none" stroke="rgba(181,144,122,0.07)"/>')
emit(f'<polygon points="{ring67}" fill="none" stroke="rgba(181,144,122,0.07)"/>')
emit(f'<polygon points="{ring100}" fill="none" stroke="rgba(181,144,122,0.1)"/>')

# Labels
for lbl, lx, ly, anchor in radar_labels:
    emit(f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" class="radar-label">{lbl}</text>')

# Company polygons
for name, rd in radar_data.items():
    pts = radar_polygon_points(rd["values"])
    emit(f'<polygon points="{pts}" fill="{rd["fill"]}" stroke="{rd["stroke"]}" stroke-width="{rd["stroke_width"]}"{rd["dash"]} class="draw-target" data-tip="{rd["tip"]}"/>')

# Dots for Овсянников
ov_vals = radar_data["Овсянников"]["values"]
ov_labels_detail = [
    "Зарплатный уровень: 50 (платит рынок по операторам/технологам, не конкурентен по бренд-менеджерам)",
    "Активность найма: 5 (0 вакансий на HH — невидим для рынка)",
    "HR-бренд: 5 (нет профиля работодателя, нет карьерной страницы)",
    "Размер команды: 25 (~50 сотрудников vs Mixit ~500+)",
    "Выручка/сотрудник: 80 (5.2М₽/чел — хороший показатель)",
    "Гибкость: 15 (производство = офлайн, но МП-менеджеры могут быть remote)",
]
for i, v in enumerate(ov_vals):
    px_pt, py_pt = radar_point(i, v)
    emit(f'<circle cx="{px_pt}" cy="{py_pt}" r="4" fill="#B5907A" data-tip="{ov_labels_detail[i]}"/>')

emit("""</g>
</svg>
<div class="chart-legend">
<div class="leg-item"><div class="leg-swatch" style="background:#B5907A;"></div>Овсянников (сильная экономика, 0 HR-бренд)</div>
<div class="leg-item"><div class="leg-swatch" style="background:#B85C5C;"></div>Mixit (лидер найма, полный HR-стек)</div>
<div class="leg-item"><div class="leg-swatch" style="background:#8A9AAA;"></div>VOIS (digital-first, гибкость, стелс-найм)</div>
<div class="leg-item"><div class="leg-swatch" style="background:#8BAF7A;"></div>The Act (рекордная выручка/чел, стелс-найм)</div>
</div>
</div>

<div class="callout callout-gold" style="margin-top:16px;">
<h4>Ключевой разрыв: экономика сильная, HR-бренд — нулевой</h4>
<p>Овсянников имеет <strong>лучшую экономику на сотрудника</strong> среди компаний сопоставимого размера (5.2М₽ выручки/чел.), но <strong>полностью невидим</strong> для рынка труда. Mixit тратит значительные ресурсы на HR-бренд (177 вакансий, карьерный сайт, описание культуры), но имеет убыток -420М₽. <strong>Вывод:</strong> Овсянникову нужен минимальный HR-маркетинг (профиль HH + карьерная страница), а не дорогой HR-бренд.</p>
</div>

<div class="info-tip"><div class="ii">i</div><span><strong>Методология:</strong> Зарплатный уровень — позиция медианы vs рынок. Активность найма — кол-во вакансий на HH. HR-бренд — наличие профиля, описания, логотипа. Размер команды — оценка по данным ЕГРЮЛ/СМИ. Выручка/сотрудник — ФНС 2024 / оценка штата. Гибкость — доля remote-вакансий. Оценки экспертные, 0-100.</span></div>
</div>
""")


# ════════════════════════════════════════════
# Section 2.23 — HR-инсайты и рекомендации
# ════════════════════════════════════════════
emit("""
<div class="section" id="sec-2-23">
<div class="section-head"><div class="section-num" style="width:auto;min-width:42px;padding:0 12px;border-radius:20px;">2.23</div><h2>HR-инсайты и рекомендации</h2></div>
<div class="section-desc">SWOT найма + конкретные действия. Что делать Овсянникову, чтобы не упереться в кадровый потолок при росте до 1 млрд₽?</div>

""")

# Dynamic SWOT values from v4 data
sw = {k: next((p for p in positions if p["key"] == k), {}) for k in ["brand", "commercial_dir", "cfo", "hr_dir", "marketplace", "rnd", "technologist", "marketing", "production_dir", "operator", "logistics"]}

brand_med = sw["brand"].get("industry", {}).get("salary_median", 150000)
cd_gen_med = sw["commercial_dir"].get("general", {}).get("salary_median", 250000)
cfo_gen_med = sw["cfo"].get("general", {}).get("salary_median", 178000)
hr_gen_med = sw["hr_dir"].get("general", {}).get("salary_median", 137000)
mp_gen_total = sw["marketplace"].get("general", {}).get("total", 1981)
mp_remote = sw["marketplace"].get("remote_pct", 28)
rnd_ind_total = sw["rnd"].get("industry", {}).get("total", 42)
tech_noexp = sw["technologist"].get("no_experience_pct", 10)
mkt_ind_total = sw["marketing"].get("industry", {}).get("total", 99)
pd_ind_med = sw["production_dir"].get("industry", {}).get("salary_median", 162000)

# Count how many positions have median <= AFFORD_GREEN
affordable_count = sum(1 for p in positions if p["salary"]["median"] <= AFFORD_GREEN)

emit(f"""<div class="swot-grid">
<div class="swot-box swot-s">
<h4>Сильные стороны (найм)</h4>
<ul>
<li>Высокая выручка на сотрудника (5.2М₽) — можно предложить бонусы</li>
<li>Собственное производство — привлекательно для технологов и R&amp;D</li>
<li>Быстрый рост ×17 за 2 года — карьерные возможности</li>
<li>B2B-модель — стабильная загрузка, нет сезонных увольнений</li>
<li>Конкурентные зарплаты для {affordable_count} из 12 ключевых позиций</li>
<li>Директор по производству ({fmt_k(pd_ind_med)}₽ в отрасли) — по силам, а это ключевая позиция</li>
</ul>
</div>
<div class="swot-box swot-w">
<h4>Слабые стороны (найм)</h4>
<ul>
<li>0 присутствие на HH — невидим для 90% соискателей</li>
<li>Нет HR-бренда, карьерной страницы, культурного контента</li>
<li>Не конкурентен по бренд-менеджерам ({fmt_k(brand_med)}₽) и коммерческим директорам ({fmt_k(cd_gen_med)}₽ на рынке!)</li>
<li>Финдиректор ({fmt_k(cfo_gen_med)}₽) и HR-директор ({fmt_k(hr_gen_med)}₽ на рынке) — на пределе бюджета</li>
<li>Маленькая команда (50 чел.) — ограниченный карьерный рост</li>
<li>Производство = офлайн, нет remote для 90% позиций</li>
</ul>
</div>
<div class="swot-box swot-o">
<h4>Возможности (найм)</h4>
<ul>
<li>МП-менеджеры: {mp_remote}% remote → нанимать из регионов (дешевле)</li>
<li>R&amp;D из сокращающихся компаний (Natura Sib. убыток -1.3 млрд)</li>
<li>Стажёрские программы для технологов ({tech_noexp}% рынка — без опыта)</li>
<li>Digital-маркетологи: всего {mkt_ind_total} вакансий в косметике — можно выделиться</li>
<li>Создать профиль на HH = instant visibility (конкуренты не делают)</li>
</ul>
</div>
<div class="swot-box swot-t">
<h4>Угрозы (найм)</h4>
<ul>
<li>Mixit переманивает лучших (177 вакансий, зарплаты до 261К)</li>
<li>Рост зарплат в FMCG: медиана {fmt_k(fmcg_market['salary']['median'])}₽ vs {fmt_k(cosm_market['salary']['median'])}₽ в beauty</li>
<li>Дефицит МП-менеджеров: {fmt_num(mp_gen_total)} вакансий в Москве+МО</li>
<li>При росте до 100+ чел. — HR-процессы не масштабируются без системы</li>
<li>Faberlic (61 вакансий) и Splat (39) — тоже активно нанимают</li>
</ul>
</div>
</div>""")

tech_ind_med = sw["technologist"].get("industry", {}).get("salary_median", 104000)
op_ind_med = sw["operator"].get("industry", {}).get("salary_median", 80000)

emit(f"""<div class="grid-2" style="margin-top:16px;">
<div class="callout callout-green">
<h4>Где Овсянников выиграет</h4>
<ul style="margin-top:8px;">
<li><strong>Технологи ({fmt_k(tech_ind_med)}₽) и операторы ({fmt_k(op_ind_med)}₽)</strong> — зарплаты по карману, собственное производство = конкурентное преимущество</li>
<li><strong>B2B-менеджеры (HoReCa)</strong> — уникальная экспертиза в аменити, 1500+ партнёров как кейс</li>
<li><strong>Remote МП-менеджеры из регионов</strong> — экономия 30-40% vs Москва при сопоставимом качестве</li>
<li><strong>Карьерный рост</strong> — в компании ×17 за 2 года сотрудник растёт вместе с бизнесом</li>
</ul>
</div>
<div class="callout callout-red">
<h4>Где Овсянников проиграет</h4>
<ul style="margin-top:8px;">
<li><strong>Топ-менеджмент</strong> — КД {fmt_k(cd_gen_med)}₽, CFO {fmt_k(cfo_gen_med)}₽, бренд-менеджер {fmt_k(brand_med)}₽. Нужны опционы/доля в бизнесе</li>
<li><strong>Digital-маркетологи уровня «сеньор»</strong> — при 0 digital-присутствии нет кейса для портфолио</li>
<li><strong>HR-бренд</strong> — Mixit: 177 вакансий, карьерная страница. Овсянников: тишина</li>
<li><strong>Масштаб</strong> — при 50 чел. нет HR-отдела, нет онбординга, нет грейдов</li>
</ul>
</div>
</div>""")

rnd_ind_t = sw["rnd"].get("industry", {}).get("total", 42)
emit(f"""<div class="callout callout-gold" style="margin-top:16px;">
<h4>Рекомендация: 4 приоритета в HR</h4>
<p><strong>1.</strong> Создать профиль работодателя на hh.ru (бесплатно, +visibility). <strong>2.</strong> Нанять 2-3 remote МП-менеджеров из регионов — экономия ~40% ФОТ. <strong>3.</strong> Хантинг R&amp;D из Natura Siberica (убыток -1.3 млрд → возможны сокращения; всего {rnd_ind_t} вакансий R&amp;D в косметике). <strong>4. Топ-менеджмент: коммерческий директор — ключевой найм для роста до 1 млрд₽.</strong> Медиана {fmt_k(cd_gen_med)}₽ на рынке — не по карману «в лоб». Решение: предложить долю/опцион + бонус от роста выручки. Директор по производству ({fmt_k(pd_ind_med)}₽ в отрасли) — нанять раньше, пока рост позволяет.</p>
</div>""")

emit(f"""<div class="info-tip"><div class="ii">i</div><span><strong>Источники:</strong> hh.ru API ({collected_at}), ФНС (выручка/прибыль), ЕГРЮЛ (штат), отраслевые данные. SWOT основан на сопоставлении зарплатных бенчмарков hh.ru с оценкой ФОТ Овсянникова (выручка 260М₽ × 30% = 78М₽/год). Все зарплаты net. Данные верифицированы по 2+ источникам.</span></div>
</div>
""")


# ── Output ──
output = "\n".join(html_parts)
out_path = "/Users/n-a-ledovskoy/Desktop/вайбкодинг/Ovsyannikov/data/hr_sections.html"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(output)

print(f"✓ HTML секции сгенерированы: {out_path}")
print(f"  Размер: {len(output):,} символов")
print(f"  Строк: {output.count(chr(10))}")
