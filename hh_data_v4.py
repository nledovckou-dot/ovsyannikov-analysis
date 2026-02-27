#!/usr/bin/env python3
"""
v4: Два среза через industry-фильтр HH API (правильный способ).
  - industry: industry=42.589&industry=42.590&industry=41.516 (косметика/парфюмерия)
  - general: без фильтра отрасли
Все позиции: search_field=name (поиск только в названии вакансии).
"""
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from statistics import median, quantiles

BASE_URL = "https://api.hh.ru"
APP_TOKEN = "APPLGI4E9FIPPNIFD87G81NABJD2DO503RDSB6MEQDPLNMLCHT7OFA5AQOIGEK99"
USER_AGENT = "EspacePlatform/1.0 (n.a.ledovskoy@gmail.com)"

# Коды отраслей HH для косметики/парфюмерии
INDUSTRY_CODES = ["42.589", "42.590", "41.516"]
# 42.589 = Бытовая химия, парфюмерия, косметика (производство)
# 42.590 = Бытовая химия, парфюмерия, косметика (продвижение, опт)
# 41.516 = Розничная сеть (парфюмерия, косметика)

POSITIONS = [
    {"key": "technologist", "query": "технолог", "label": "Технолог производства"},
    {"key": "operator", "query": "оператор производственной линии", "label": "Оператор производственной линии"},
    {"key": "sales_b2b", "query": "менеджер по продажам", "label": "Менеджер по продажам B2B"},
    {"key": "marketplace", "query": "менеджер маркетплейсов", "label": "Менеджер маркетплейсов (WB/Ozon)"},
    {"key": "marketing", "query": "маркетолог", "label": "Digital-маркетолог"},
    {"key": "logistics", "query": "логист OR кладовщик", "label": "Логист / Кладовщик"},
    {"key": "rnd", "query": "разработчик рецептур OR химик-технолог", "label": "R&D / Разработчик рецептур"},
    {"key": "brand", "query": "бренд-менеджер", "label": "Бренд-менеджер"},
    {"key": "commercial_dir", "query": "коммерческий директор", "label": "Коммерческий директор"},
    {"key": "production_dir", "query": "директор по производству", "label": "Директор по производству"},
    {"key": "hr_dir", "query": "HR директор OR директор по персоналу", "label": "HR-директор / HRD"},
    {"key": "cfo", "query": "финансовый директор OR CFO", "label": "Финансовый директор / CFO"},
]


def hh_get(path, params_list):
    """GET with support for repeated params (industry=X&industry=Y)."""
    # Build URL manually to support repeated keys
    base = f"{BASE_URL}{path}"
    if params_list:
        parts = []
        for k, v in params_list:
            parts.append(f"{urllib.parse.quote(k)}={urllib.parse.quote(str(v))}")
        url = base + "?" + "&".join(parts)
    else:
        url = base

    headers = {"User-Agent": USER_AGENT, "Authorization": f"Bearer {APP_TOKEN}", "Accept": "application/json"}
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(3 * (2 ** attempt))
                continue
            if attempt < 2:
                time.sleep(2)
                continue
            raise
        except:
            if attempt < 2:
                time.sleep(2)
                continue
            raise
    return None


def gross_to_net(a):
    return round(a * 0.87) if a else None


def extract_salaries(vacancies):
    salaries = []
    for v in vacancies:
        s = v.get("salary")
        if not s or s.get("currency", "RUR") != "RUR":
            continue
        fr, to = s.get("from"), s.get("to")
        if fr and to: val = (fr + to) / 2
        elif fr: val = fr
        elif to: val = to
        else: continue
        if s.get("gross", True): val = gross_to_net(val)
        salaries.append(int(val))
    return salaries


def calc_stats(salaries):
    if not salaries:
        return {"count": 0, "min": 0, "q1": 0, "median": 0, "q3": 0, "max": 0}
    salaries.sort()
    q = quantiles(salaries, n=4) if len(salaries) >= 4 else [salaries[0], median(salaries), salaries[-1]]
    return {
        "count": len(salaries), "min": salaries[0],
        "q1": q[0] if len(q) >= 3 else salaries[0],
        "median": int(median(salaries)),
        "q3": q[2] if len(q) >= 3 else salaries[-1],
        "max": salaries[-1],
    }


def collect_slice(query, industry_codes=None):
    """Collect vacancies with optional industry filter. Area: Moscow (1) + Moscow Oblast (46)."""
    # With salary
    params = [("text", query), ("area", "1"), ("area", "46"), ("only_with_salary", "true"), ("per_page", "100"), ("search_field", "name")]
    if industry_codes:
        for code in industry_codes:
            params.append(("industry", code))

    data = hh_get("/vacancies", params)
    time.sleep(0.25)
    if not data:
        return {"total": 0, "with_salary": 0, "remote": 0, "remote_pct": 0, "salary": calc_stats([]), "no_experience_pct": 0}

    vacancies = data.get("items", [])
    with_salary = data.get("found", 0)
    salaries = extract_salaries(vacancies)

    # All (no salary filter)
    params_all = [("text", query), ("area", "1"), ("area", "46"), ("per_page", "100"), ("search_field", "name")]
    if industry_codes:
        for code in industry_codes:
            params_all.append(("industry", code))
    data_all = hh_get("/vacancies", params_all)
    time.sleep(0.25)
    total = data_all.get("found", 0) if data_all else with_salary
    all_vac = data_all.get("items", []) if data_all else vacancies

    # Remote
    params_r = [("text", query), ("area", "1"), ("area", "46"), ("schedule", "remote"), ("per_page", "0"), ("search_field", "name")]
    if industry_codes:
        for code in industry_codes:
            params_r.append(("industry", code))
    data_r = hh_get("/vacancies", params_r)
    time.sleep(0.25)
    remote = data_r.get("found", 0) if data_r else 0

    no_exp = sum(1 for v in all_vac if v.get("experience", {}).get("id") == "noExperience")
    no_exp_pct = round(no_exp / len(all_vac) * 100, 1) if all_vac else 0

    return {
        "total": total,
        "with_salary": with_salary,
        "remote": remote,
        "remote_pct": round(remote / total * 100, 1) if total > 0 else 0,
        "salary": calc_stats(salaries),
        "no_experience_pct": no_exp_pct,
    }


def main():
    print("HH API v4 — industry filter, Москва + МО (area=1,46)")
    print("=" * 60)

    results = []

    for pos in POSITIONS:
        print(f"\n{pos['label']}:")

        # 1. Industry slice (косметика/парфюмерия)
        print(f"  Отрасль (industry={','.join(INDUSTRY_CODES)})...")
        industry = collect_slice(pos["query"], INDUSTRY_CODES)
        print(f"    → {industry['total']} вакансий, медиана {industry['salary']['median']:,}₽")

        # 2. General market (no industry filter)
        print(f"  Общий рынок...")
        general = collect_slice(pos["query"])
        print(f"    → {general['total']} вакансий, медиана {general['salary']['median']:,}₽")

        # Primary data: industry if enough data, otherwise general
        use_industry = industry["total"] >= 5 and industry["salary"]["count"] >= 3
        primary = industry if use_industry else general

        results.append({
            "key": pos["key"],
            "label": pos["label"],
            "total_vacancies": primary["total"],
            "with_salary": primary["with_salary"],
            "remote": primary["remote"],
            "remote_pct": primary["remote_pct"],
            "salary": primary["salary"],
            "no_experience_pct": primary["no_experience_pct"],
            "industry": {
                "total": industry["total"],
                "salary_median": industry["salary"]["median"],
                "salary_q1": industry["salary"]["q1"],
                "salary_q3": industry["salary"]["q3"],
                "salary_max": industry["salary"]["max"],
            },
            "general": {
                "total": general["total"],
                "salary_median": general["salary"]["median"],
                "salary_q1": general["salary"]["q1"],
                "salary_q3": general["salary"]["q3"],
                "salary_max": general["salary"]["max"],
            },
        })

        time.sleep(0.3)

    # Load existing JSON (keep market + competitors)
    data_path = "/Users/n-a-ledovskoy/Desktop/вайбкодинг/Ovsyannikov/data/hh_labor_market.json"
    with open(data_path, "r", encoding="utf-8") as f:
        full = json.load(f)

    full["positions"] = results
    full["collected_at"] = datetime.now().isoformat()

    all_med = [p["salary"]["median"] for p in results if p["salary"]["median"] > 0]
    total = sum(p["total_vacancies"] for p in results)
    avg_r = sum(p["remote_pct"] for p in results) / len(results) if results else 0
    full["summary"] = {
        "total_vacancies_positions": total,
        "median_salary_overall": int(median(all_med)) if all_med else 0,
        "avg_remote_pct": round(avg_r, 1),
    }

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✓ Сохранено: {data_path}")
    print(f"\n{'Позиция':42s} {'Отрасль':>8s} {'Общий':>8s}  {'Мед.отр':>8s} {'Мед.общ':>8s}  Источник")
    print("-" * 95)
    for p in results:
        ind = p["industry"]["total"]
        gen = p["general"]["total"]
        med_i = p["industry"]["salary_median"]
        med_g = p["general"]["salary_median"]
        use = "отрасль" if (ind >= 5 and med_i > 0) else "общий"
        print(f"{p['label']:42s} {ind:>8,} {gen:>8,}  {med_i:>7,}₽ {med_g:>7,}₽  {use}")


if __name__ == "__main__":
    main()
