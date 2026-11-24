"""금천미트(ekcm.co.kr) 단가 수집기 — 카테고리·부위·등급별 Kg당 최저/최고 (한우·육우·돈육·수입육·계육·양육·염소·세절육)

사용법
  python ekcm_collector.py                  전체 수집 (오늘 날짜로 저장)
  python ekcm_collector.py --resume         오늘 이미 받은 부위/등급은 건너뛰고 이어서 수집
  python ekcm_collector.py --parts "안심;등심"  지정한 부위만 수집
  python ekcm_collector.py --cat "한우암소"     지정한 카테고리만 수집 (예: 새 카테고리 시험)
  python ekcm_collector.py --show           브라우저 창을 띄워서 실행(원인 확인용)
  python ekcm_collector.py --test 파일.html  저장한 HTML로 읽기 검증
설치:  pip install playwright beautifulsoup4 lxml  →  playwright install chromium

방식: 부위 버튼 → 등급 버튼 → "Kg당 가격 낮은/높은 순" 정렬 후 맨 위 상품을 읽음.
      '명품' 상품(등급 칸에 명품으로 표시)은 제외하고 최저/최고를 계산합니다.
      (참고용으로 명품 포함 최저/최고는 min_all_kg / max_all_kg 에 따로 저장)
결과: prices.db (SQLite, price_range 표) / latest.json (오늘 요약, 대시보드용)
"""
import argparse, json, random, re, sqlite3, sys, time
from datetime import date
from bs4 import BeautifulSoup

# ───────── 설정 (여기만 고치면 됩니다) ─────────
START_URL = ("https://www.ekcm.co.kr/pd/product?dispCtgNo=13&uprTopDispCtgNo=1"
             "&dispCtgNm=%EA%B5%AD%EB%82%B4%EC%82%B0%20%ED%95%9C%EC%9A%B0%20%EA%B1%B0%EC%84%B8"
             "&leafCtgNo=130101&dispCtgNoList=130101,130201,130301,130401,130501,130601,130701,130801,815887,816994,817764,819103")

# 수집할 부위 (사이트 부위 버튼의 이름 그대로). 필요 없는 줄은 지우면 됩니다.
PARTS = [
    # 냉장
    "안심", "등심", "윗등심", "아랫등심", "채끝", "목심", "앞다리살", "앞다리살(앞다리+꾸리)", "꾸리살",
    "부채살", "우둔살", "홍두깨", "설도", "설도(삼각살 X)", "설깃", "삼각살", "양지머리,치마양지", "양지머리 외",
    "치마살", "차돌박이(냉장)", "업진살", "앞치마살,업진안살", "앞치마살", "업진안살", "사태", "갈비", "갈비살",
    "안창살", "갈비본살+갈비살치", "토시살", "늑간살", "토시,제비추리", "제비추리", "안창외2종",
    # 냉동
    "차돌박이", "냉동목심", "냉동설깃", "냉동앞다리", "냉동설도", "냉동사태", "냉동우둔",
    "냉동양지머리,치마양지", "냉동갈비",
]
GRADES = ["1++", "1+", "1", "2", "3"]
SUB = "https://www.ekcm.co.kr/dp/subMain?dispCtgNo="
# 수집할 카테고리 (이름 → 시작 주소, 등급 목록). 부위는 사이트 화면에서 자동으로 읽습니다(상품 0건인 부위는 건너뜀).
CATEGORIES = {
    "한우거세": {"url": START_URL, "grades": ["1++", "1+", "1", "2", "3"]},
    "한우암소": {"url": SUB + "14", "grades": ["1++", "1+", "1", "2", "3"]},
    "육우거세": {"url": SUB + "21", "grades": ["1++", "1+", "1", "2", "3", "등외"]},
    "육우암소": {"url": SUB + "22", "grades": ["1++", "1+", "1", "2", "3", "등외"]},
    "국내산 돈육": {"url": SUB + "31", "grades": ["전체"], "nograde": True},   # 돈육은 등급 구분이 없음
    # 수입냉장우육: 부위별로만 나눔(국가·등급은 나누지 않고, 최저/최고 상품의 브랜드·원산지·등급을 같이 저장)
    "수입냉장우육": {"url": SUB + "41", "grades": ["전체"], "nograde": True, "group": "냉장", "countries": ["미국", "호주"]},
    # 수입냉동우육: 부위별로만 나눔(국가·등급은 나누지 않고, 최저/최고 상품의 브랜드·원산지·등급을 같이 저장)
    # 수입돈육: 우육과 같은 방식. 국가 목록은 부위마다 화면의 "국가" 필터에서 자동으로 읽음(그 부위에 있는 나라만 나옴)
    "수입냉장돈육": {"url": SUB + "51", "grades": ["전체"], "nograde": True, "group": "냉장", "countries": "auto"},
    "수입냉동돈육": {"url": SUB + "52", "grades": ["전체"], "nograde": True, "group": "냉동", "countries": "auto"},
    "수입냉동우육": {"url": SUB + "42", "grades": ["전체"], "nograde": True, "group": "냉동", "countries": ["미국", "호주"]},
    # 아래 4개: 등급 없음. "groups" = 사이트 부위 목록의 묶음(소제목) 중 수집할 것만. 같은 이름이 두 묶음에 있으면 "이름(묶음)"으로 저장
    "계육": {"url": SUB + "814724", "grades": ["전체"], "nograde": True, "groups": ["국내산 냉장", "국내산 냉동", "수입계육"]},
    "양육": {"url": SUB + "62", "grades": ["전체"], "nograde": True, "groups": ["냉장", "냉동"]},
    "염소": {"url": SUB + "813594", "grades": ["전체"], "nograde": True, "groups": ["국내염소", "수입염소", "수입 미박염소"]},
    # 세절육: 축종/부위별 화면의 "냉동" 묶음만. 최저가 상품의 대표 이미지·상품명도 저장
    "세절육": {"url": SUB + "813284", "grades": ["전체"], "nograde": True, "group": "냉동", "img": True},
}
SORT_LOW, SORT_HIGH = "Kg당 가격 낮은 순", "Kg당 가격 높은 순"
DELAY = (0.3, 0.8)                  # 조합 사이 대기(초)
DB = "prices.db"
KNOWN_BRANDS = ["대한사람대한으로", "도축장집아들들", "금천한우", "성신한우", "과연한우", "안심한우",
                "민속친한우", "마장동한우", "성진본한우", "반하누", "외부한우", "금천미한우",
                "금천육우", "금천보리소", "늘찬육우", "참연진심육우", "참연 진심육우", "다담미트", "연담우육우", "연담우"]
# ───────────────────────────────────────────────


def num(text):
    m = re.search(r"\d[\d,\.]*", text or "")
    return float(m.group().replace(",", "")) if m else None


def _txt(el, sel):
    e = el.select_one(sel)
    return e.get_text(" ", strip=True) if e else None


def _brand(name, fallback):
    for b in KNOWN_BRANDS:
        if (name or "").startswith(b):
            return b
    if fallback:
        return fallback
    return (name or "").split("거세")[0].strip() or None


def parse_row(li):
    """상품 1건 읽기. 목록형(안심 등)과 카드형(등심 등) 화면을 모두 처리"""
    a = li.select_one("a.product-unit")
    gno = re.search(r"goodsNo=(\d+)", a["href"]).group(1) if a else None
    name = _txt(li, "p.name")
    chips = [c.get_text(strip=True) for c in li.select(".chip")]
    grade_txt = _txt(li, ".chip.type1")                 # 1++A / 명품 ...
    marb = re.search(r"NO\.(\d)", _txt(li, ".chip.type2") or "")
    price_kg = num(_txt(li, ".pd-price.c-primary"))
    sale = num(_txt(li, ".pd-price.c-black"))
    if price_kg is None or not name:
        raise ValueError("가격/상품명을 못 읽음")
    origin = None                                           # 원산지 (수입육): "원산지/등급" 칸의 앞 글자 (예: 호주)
    for xs in li.select("div.pd-row"):
        lab = xs.select_one(".label")
        if lab and "원산지" in lab.get_text():
            v = xs.select_one(".value")
            if v:
                for x in v.select("span, p"):
                    x.extract()
                origin = v.get_text(strip=True) or None
            break
    plant = li.select_one("div.pd-row.lg .value")
    trace = li.select_one("div.pd-row.rg .value > span")
    made = li.select_one("div.pd-row.md .value > p")
    img = li.select_one(".thumbnail img")
    return {
        "img": (img.get("src") or "").strip() or None if img else None,
        "goods_no": gno,
        "name": name,
        "brand": _brand(name, _txt(li, ".value.brand span.show-mo")),
        "grade": grade_txt,
        "premium": int(any("명품" in c for c in chips)),
        "marbling": int(marb.group(1)) if marb else None,
        "price_kg": int(price_kg),
        "weight_kg": num(_txt(li, ".chip-weight")),
        "sale_price": int(sale) if sale is not None else None,
        "made_date": made.get_text(strip=True) if made else None,
        "plant": " ".join(plant.get_text(" ", strip=True).split()) if plant else None,
        "trace_no": trace.get_text(strip=True) if trace else None,
        "origin": origin,
    }


def parse_list(html):
    """상품 목록 HTML -> (총 건수, 상품 리스트). 읽지 못한 상품은 건너뛰고 개수를 알려줌"""
    soup = BeautifulSoup(html, "lxml")
    t = soup.select_one(".list-wrap .top-area .total")
    total = int(t.get_text(strip=True).replace(",", "")) if t else None
    rows, bad = [], 0
    for li in soup.select("li.pd-list-unit"):
        try:
            rows.append(parse_row(li))
        except Exception:
            bad += 1
    if bad:
        print(f"   (읽지 못한 상품 {bad}건 건너뜀)")
    return total, rows


def top_pair(rows):
    """정렬된 목록에서 (전체 기준 1위, 명품 제외 기준 1위)"""
    if not rows:
        return None, None
    ex = next((r for r in rows if not r["premium"]), None)
    return rows[0], ex


def summarize(rows):
    """(테스트용) 읽은 목록 전체에서 최저/최고 계산"""
    if not rows:
        return None
    lo = min(rows, key=lambda r: r["price_kg"])
    hi = max(rows, key=lambda r: r["price_kg"])
    return {"count": len(rows), "min": lo["price_kg"], "max": hi["price_kg"],
            "premium_rows": sum(r["premium"] for r in rows)}


# ───────────────────────── 저장 ─────────────────────────
COLS = ["day", "category", "part", "grade_f", "total",
        "min_kg", "min_goods", "min_brand", "min_grade",      # 최저가 (명품 제외)
        "max_kg", "max_goods", "max_brand", "max_grade",      # 최고가 (명품 제외)
        "min_all_kg", "max_all_kg",                           # 참고: 명품 포함 최저/최고
        "min_origin", "max_origin",                           # 최저/최고 상품의 원산지(수입육)
        "pgrp", "min_img", "min_name"]                        # 부위 묶음(사이트 소제목), 최저가 상품 이미지·이름(세절육)
TEXT_COLS = {"day", "category", "part", "grade_f", "min_goods", "min_brand", "min_grade",
             "max_goods", "max_brand", "max_grade", "min_origin", "max_origin", "pgrp", "min_img", "min_name"}


def init_db(con):
    old = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='price_range'").fetchone()
    if old:
        have = {r[1] for r in con.execute("PRAGMA table_info(price_range)")}
        if "category" not in have:                    # 이전 버전 DB: 카테고리 열이 없으면 표를 새로 만들어 옮김
            con.execute("ALTER TABLE price_range RENAME TO price_range_old")
            con.execute("""CREATE TABLE price_range(
                day TEXT, category TEXT, part TEXT, grade_f TEXT, total INT,
                PRIMARY KEY(day, category, part, grade_f))""")
            for c in COLS:
                if c not in ("day", "category", "part", "grade_f", "total"):
                    con.execute(f"ALTER TABLE price_range ADD COLUMN {c} {'TEXT' if c in TEXT_COLS else 'INT'}")
            oldcols = {r[1] for r in con.execute("PRAGMA table_info(price_range_old)")}
            use = [c for c in COLS if c in oldcols and c != "category"]
            con.execute(f"INSERT OR IGNORE INTO price_range(category,{','.join(use)}) "
                        f"SELECT '한우거세',{','.join(use)} FROM price_range_old")
            con.execute("DROP TABLE price_range_old")
    else:
        con.execute("""CREATE TABLE price_range(
            day TEXT, category TEXT, part TEXT, grade_f TEXT, total INT,
            PRIMARY KEY(day, category, part, grade_f))""")
    have = {r[1] for r in con.execute("PRAGMA table_info(price_range)")}
    for c in COLS:
        if c not in have:
            con.execute(f"ALTER TABLE price_range ADD COLUMN {c} {'TEXT' if c in TEXT_COLS else 'INT'}")
    con.commit()


def save_row(con, rec):
    vals = {c: rec.get(c) for c in COLS}
    con.execute(f"INSERT OR REPLACE INTO price_range({','.join(COLS)}) VALUES({','.join(':'+c for c in COLS)})", vals)
    con.commit()


def _dbcats(cat, cfg):
    return [cat]


CAT_ORDER = [d for c, f in CATEGORIES.items() for d in _dbcats(c, f)]


def _sorted_rows(rows):
    ci = lambda r: CAT_ORDER.index(r["category"]) if r["category"] in CAT_ORDER else 99
    pi = lambda r: PARTS.index(r["part"]) if r["part"] in PARTS else 999
    gi = lambda r: GRADES.index(r["grade_f"]) if r["grade_f"] in GRADES else 9
    return sorted(rows, key=lambda r: (ci(r), pi(r), gi(r)))      # 같은 순위끼리는 수집 순서 유지


def export_latest(con, day):
    con.row_factory = sqlite3.Row
    out = [dict(r) for r in con.execute(
        "SELECT * FROM price_range WHERE day=? AND total>0 ORDER BY rowid", (day,))]
    con.row_factory = None
    out = _sorted_rows(out)
    json.dump(out, open("latest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    export_history(con)
    return len(out)


HIST_KEEP = ["day", "category", "part", "grade_f", "total", "min_kg", "max_kg", "min_brand", "max_brand",
             "min_all_kg", "max_all_kg", "min_grade", "max_grade", "min_origin", "max_origin", "pgrp"]


def export_history(con):
    """모든 날짜 기록을 history.json 으로 저장 (대시보드 추이/알림용, 용량 줄이려고 핵심 열만)"""
    con.row_factory = sqlite3.Row
    rows = [{k: r[k] for k in HIST_KEEP} for r in con.execute(
        "SELECT * FROM price_range WHERE total>0 ORDER BY day, rowid")]
    con.row_factory = None
    json.dump(rows, open("history.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


def import_history(con):
    """prices.db 가 없는 환경(GitHub 자동실행)에서 history.json 으로 과거 기록 복원"""
    import os
    if not os.path.exists("history.json"):
        return
    for r in json.load(open("history.json", encoding="utf-8")):
        p = {k: r.get(k) for k in HIST_KEEP}
        p["category"] = p["category"] or "한우거세"             # 옛 기록은 카테고리가 없음 → 한우거세
        con.execute("INSERT OR IGNORE INTO price_range (%s) VALUES (%s)" % (
            ",".join(HIST_KEEP), ",".join(":" + k for k in HIST_KEEP)), p)
    con.commit()


# ───────────────────── 화면 조작 (브라우저) ─────────────────────
JS_SIG = """() => {
  const t = document.querySelector('.list-wrap .total');
  const top = document.querySelector('.list-wrap .top-area');
  const lis = [...document.querySelectorAll('li.pd-list-unit')];
  const ids = lis.slice(0, 4).map(l => {
    const a = l.querySelector('a.product-unit');
    const m = a && a.getAttribute('href').match(/goodsNo=(\\d+)/);
    return m ? m[1] : '';
  }).join(',');
  const total = t ? t.textContent.trim() : '';
  return {sig: total + '|' + ids, loading: top ? top.getAttribute('isloading') : null,
          ready: (total === '0') || lis.length > 0};
}"""

JS_PARTS = """(group) => {
  const gs = [...document.querySelectorAll('.category-wrap .group')];
  let items = [...document.querySelectorAll('.category-wrap .ctg-item')];
  if (group && gs.length) {                      // 수입육: 지정한 그룹(냉장/냉동)의 부위만
    const g = gs.find(x => (((x.querySelector('.subtitle3') || {}).textContent) || '').trim().startsWith(group));
    items = g ? [...g.querySelectorAll('.ctg-item')] : [];
  }
  return items.map(e => e.textContent.replace(/\\s+/g, ' ').trim()).filter(Boolean);
}"""

JS_FIRST_PART = """() => {
  const nm = el => el.textContent.replace(/\\s+/g, ' ').trim();
  const el = [...document.querySelectorAll('.category-wrap .ctg-item')].find(e => {
    const m = nm(e).match(/\\(([\\d,]+)\\)\\s*$/); return m && Number(m[1].replace(/,/g, '')) > 0; });
  if (!el) return null;
  (el.querySelector('.category') || el).click();
  return nm(el);
}"""

JS_CLICK_PART = """([name, group]) => {
  const nm = el => el.textContent.replace(/\\s+/g, ' ').trim();
  const base = n => n.replace(/\\s*\\([\\d,]+\\)\\s*$/, '');
  const gs = [...document.querySelectorAll('.category-wrap .group')];
  let items = [...document.querySelectorAll('.category-wrap .ctg-item')];
  if (group && gs.length) {
    const g = gs.find(x => (((x.querySelector('.subtitle3') || {}).textContent) || '').trim().startsWith(group));
    items = g ? [...g.querySelectorAll('.ctg-item')] : [];
  }
  const el = items.find(e => base(nm(e)) === name);
  if (!el) return null;
  const label = nm(el);
  (el.querySelector('.category') || el).click();
  return label;
}"""

JS_CLICK_GRADE = """async (grade) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const clean = x => x.textContent.replace(/품절/g, '').trim();
  const findRow = () => [...document.querySelectorAll('.filter-group dl')]
      .find(d => (d.querySelector('dt') || {}).textContent.trim().startsWith('등급'));
  const labels = row => row ? [...row.querySelectorAll('button')].map(clean).filter(Boolean) : [];
  const applied = () => {                      // 등급 칸의 선택 개수가 1이면 적용된 것
    const r = findRow(); const c = r && r.querySelector('dt .count');
    return !!c && c.textContent.trim() === '1';
  };
  // 부위를 바꾼 직후에는 등급 버튼이 늦게 채워질 수 있어서, 최대 12초까지 기다림
  const t0 = Date.now();
  let row = null, toggled = false;
  while (Date.now() - t0 < 12000) {
    row = findRow();
    if (labels(row).length) break;
    const t = document.querySelector('.filter-wrap .btn-toggle');
    if (!toggled && t && t.classList.contains('up') && Date.now() - t0 > 2500) {   // 접혀 있을 때만 펼침
      t.click(); toggled = true;
    }
    await sleep(250);
  }
  if (!row || !labels(row).length) return 'NO_GRADE_ROW';
  if (!labels(row).some(l => l === grade)) return 'NO_BUTTON:' + labels(row).join(',');
  // 클릭 후 실제로 적용됐는지 확인 (이전 부위의 낡은 버튼을 누른 경우를 걸러냄). 최대 4번 시도
  for (let i = 0; i < 4; i++) {
    const r = findRow();
    const btn = r && [...r.querySelectorAll('button')].find(b => clean(b) === grade);
    if (btn) btn.click();
    await sleep(700);
    if (applied()) return 'OK';
    await sleep(800);
  }
  return 'CLICK_FAILED';
}"""

JS_CLICK_SORT = """(label) => {
  const b = [...document.querySelectorAll('.sort-group .sort-item button')]
      .find(x => x.textContent.trim() === label);
  if (!b) return false;
  b.click();
  return true;
}"""

JS_CLICK_COUNTRY = """async (country) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const clean = x => x.textContent.replace(/품절/g, '').trim();
  const findRow = () => [...document.querySelectorAll('.filter-group dl')]
      .find(d => (d.querySelector('dt') || {}).textContent.trim().startsWith('국가'));
  for (let i = 0; i < 4; i++) {
    const r = findRow();
    const btn = r && [...r.querySelectorAll('button')].find(b => clean(b) === country);
    if (!btn) { await sleep(600); if (i === 3) return 'NO_BUTTON'; continue; }
    btn.click();
    await sleep(700);
    const c = r.querySelector('dt .count');
    if (c && c.textContent.trim() === '1') return 'OK';
    await sleep(600);
  }
  return 'CLICK_FAILED';
}"""

JS_COUNTRY_LABELS = """async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const clean = x => x.textContent.replace(/품절/g, '').trim();
  const t0 = Date.now();
  while (Date.now() - t0 < 8000) {
    const row = [...document.querySelectorAll('.filter-group dl')]
        .find(d => (d.querySelector('dt') || {}).textContent.trim().startsWith('국가'));
    const bs = row ? [...row.querySelectorAll('button')] : [];
    if (bs.length) return bs.map(clean).filter(Boolean);
    await sleep(250);
  }
  return [];
}"""

JS_GRADE_LABELS = """async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const clean = x => x.textContent.replace(/품절/g, '').trim();
  const findRow = () => [...document.querySelectorAll('.filter-group dl')]
      .find(d => (d.querySelector('dt') || {}).textContent.trim().startsWith('등급'));
  const t0 = Date.now();
  while (Date.now() - t0 < 12000) {
    const row = findRow();
    const bs = row ? [...row.querySelectorAll('button')] : [];
    if (bs.length) {
      return bs.filter(b => { const s = b.querySelector('.soldout-badge'); return !(s && s.style.display !== 'none'); })
               .map(clean).filter(Boolean);
    }
    await sleep(250);
  }
  return null;
}"""

JS_CLEAR = """() => {
  const b = [...document.querySelectorAll('button')]
      .find(x => x.textContent.trim() === '전체해제' && x.offsetParent !== null);
  if (b) b.click();
  return !!b;
}"""


def settle(page, secs=2.5):
    """이 사이트는 분석 스크립트가 계속 돌아 networkidle이 끝나지 않으므로 고정 대기를 씁니다"""
    time.sleep(secs)


def signature(page):
    return page.evaluate(JS_SIG)


def wait_change(page, prev, timeout=8.0):
    """목록이 바뀔 때까지(총 건수 또는 맨 위 상품이 달라질 때까지) 기다림. 안 바뀌면 timeout 후 계속"""
    t0 = time.time()
    time.sleep(0.4)
    while time.time() - t0 < timeout:
        cur = signature(page)
        if cur["sig"] != prev["sig"] and cur["loading"] != "true" and cur["ready"]:
            time.sleep(0.4)
            return True
        time.sleep(0.25)
    return False


def click_part(page, name, group=None):
    """부위 버튼을 눌러 목록을 바꾸고, 사이트에 표시된 상품 수를 돌려줌"""
    prev = signature(page)
    label = page.evaluate(JS_CLICK_PART, [name, group])
    if not label:
        raise RuntimeError(f"부위 버튼을 못 찾음: {name}")
    wait_change(page, prev, timeout=6.0)
    m = re.search(r"\(([\d,]+)\)\s*$", label)
    return int(m.group(1).replace(",", "")) if m else None


def click_grade(page, grade):
    """등급 버튼 클릭. 'OK' 또는 'NO_BUTTON:..' / 'NO_GRADE_ROW' 를 돌려줌"""
    prev = signature(page)
    r = page.evaluate(JS_CLICK_GRADE, grade)
    if r == "OK":
        wait_change(page, prev)
    return r


def pick(page, sort_label):
    """정렬 버튼을 누르고 (총 건수, 읽은 상품들) 반환"""
    prev = signature(page)
    if not page.evaluate(JS_CLICK_SORT, sort_label):
        raise RuntimeError(f"정렬 버튼을 못 찾음: {sort_label}")
    wait_change(page, prev)
    return parse_list(page.content())


def clear_filters(page):
    prev = signature(page)
    if page.evaluate(JS_CLEAR):
        wait_change(page, prev)


def dump_debug(page, tag):
    """예상 못 한 실패 때 화면과 HTML을 저장 (원인 분석용)"""
    import os
    os.makedirs("debug", exist_ok=True)
    try:
        page.screenshot(path=f"debug/{tag}.png", full_page=True)
        open(f"debug/{tag}.html", "w", encoding="utf-8").write(page.content())
        print(f"   → debug/{tag}.png, debug/{tag}.html 저장됨")
    except Exception as e:
        print("   (디버그 저장 실패)", e)


def enter_list(page, url):
    """카테고리 시작 주소를 열고 상품 목록 화면까지 들어감"""
    page.goto(url, wait_until="domcontentloaded")
    if "subMain" in url:                                   # 카테고리 첫 화면 → 첫 부위를 눌러 목록으로
        page.wait_for_selector(".category-wrap .ctg-item", timeout=30000)
        settle(page)
        if not page.evaluate(JS_FIRST_PART):
            raise RuntimeError("부위 버튼을 못 찾음")
    page.wait_for_selector("li.pd-list-unit", timeout=30000)
    settle(page)


def discover_parts(page, group=None):
    """화면의 부위 버튼에서 (이름) 목록을 읽음. 상품 0건이거나 중복인 부위는 제외"""
    seen, out = set(), []
    for lab in page.evaluate(JS_PARTS, group):
        m = re.match(r"^(.*?)\s*\(([\d,]+)\)\s*$", lab)
        if not m:
            continue
        name, n = m.group(1).strip(), int(m.group(2).replace(",", ""))
        if n <= 0 or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def get_grade_labels(page):
    """이 부위의 등급 버튼 이름들(재고 있는 것만). 못 찾으면 None"""
    return page.evaluate(JS_GRADE_LABELS)


def click_country(page, country):
    prev = signature(page)
    r = page.evaluate(JS_CLICK_COUNTRY, country)
    if r == "OK":
        wait_change(page, prev)
    return r


def run_category(page, con, day, cat, cfg, only, resume):
    countries = cfg.get("countries") or [None]
    group = cfg.get("group")
    nograde = cfg.get("nograde")
    done = set()
    if resume:
        names = _dbcats(cat, cfg)
        done = {(r[0], r[1], r[2]) for r in con.execute(
            "SELECT category, part, grade_f FROM price_range WHERE day=? AND category IN (%s)" % ",".join("?" * len(names)),
            [day] + names)}
        print(f"이어서 수집: {cat} 오늘 이미 받은 {len(done)}건은 건너뜁니다")
    print(f"\n===== {cat} =====", flush=True)
    enter_list(page, cfg["url"])
    groups = cfg.get("groups") or [group]
    plan = []                                              # (묶음, 사이트 부위 이름, 저장할 이름)
    for g in groups:
        for p in discover_parts(page, g):
            plan.append((g, p))
    dup = {p for _, p in plan if sum(1 for _, q in plan if q == p) > 1}
    plan = [(g, p, f"{p}({g})" if p in dup else p) for g, p in plan]
    plan = [x for x in plan if (not only or x[1] in only or x[2] in only)]
    print(f"{cat}: 수집할 부위 {len(plan)}개", flush=True)
    for group, site_part, part in plan:
        print(f"[부위] {part}", flush=True)
        try:
            expect = click_part(page, site_part, group)
            shown = page.evaluate("() => (document.querySelector('.list-wrap .total')||{}).textContent")
            if expect is not None and not group and str(expect) != (shown or "").replace(",", ""):
                print(f"[주의] {part}: 사이트 표시 {expect}건 / 목록 {shown}건 (부위 전환 확인 필요)")
        except Exception as e:
            print(f"[실패] {cat}/{part}: {str(e)[:200]}", file=sys.stderr, flush=True)
            dump_debug(page, f"part_{cat}_{part}")
            continue
        grades_cfg = cfg["grades"]
        if grades_cfg == "auto":
            labels = get_grade_labels(page)
            if not labels:
                print(f"  {part}: 등급 버튼이 없어 건너뜀 (품절이거나 화면이 늦게 뜸)")
                continue
            grades_cfg = labels
        dbcat = cat
        sv = lambda rec, dbcat=dbcat: save_row(con, {**rec, "category": dbcat})
        # 수입육: "전체"(필터 없음) 한 줄 + 원산지별 한 줄씩("국가:미국" 처럼 저장)
        ctry = cfg.get("countries") or []
        if ctry == "auto":
            ctry = page.evaluate(JS_COUNTRY_LABELS) or []
            print(f"  {part}: 국가 {ctry}")
        variants = [(None, g) for g in grades_cfg] + [(c, "국가:" + c) for c in ctry]
        todo = [(c, g) for c, g in variants if (dbcat, part, g) not in done]
        if True:
            for country, grade in todo:
                tag = f"{dbcat}/{part}/{grade}"
                try:
                    if country:
                        cs = click_country(page, country)
                        if cs != "OK":
                            print(f"  {part}/{country}: 국가 버튼 없음({cs})")
                            continue
                    st = "OK" if nograde else click_grade(page, grade)
                    if st == "NO_GRADE_ROW":
                        print(f"[실패] {dbcat}/{part}: 등급 버튼이 12초 안에 안 나타남 (이 부위는 건너뜀, 나중에 --resume 으로 재시도)", file=sys.stderr, flush=True)
                        dump_debug(page, f"{dbcat}_{part}_nogradeRow")
                        break
                    if st.startswith("NO_BUTTON"):
                        print(f"  {part}/{grade}: 해당 등급 없음")
                        sv({"day": day, "part": part, "grade_f": grade, "total": 0})
                        continue
                    if st != "OK":
                        raise RuntimeError(f"등급 선택이 적용되지 않음: {st}")
                    total, low_rows = pick(page, SORT_LOW)
                    _, high_rows = pick(page, SORT_HIGH)
                except Exception as e:                          # 한 조합 실패해도 계속
                    print(f"[실패] {tag}: {str(e)[:200]}", file=sys.stderr, flush=True)
                    dump_debug(page, tag.replace("+", "p").replace("/", "_"))
                    try:
                        clear_filters(page)
                    except Exception:
                        pass
                    continue
                try:
                    if not nograde or country:
                        clear_filters(page)                      # 다음 조합을 위해 필터 초기화
                except Exception:
                    pass
                lo_all, lo = top_pair(low_rows)      # (명품 포함 1위, 명품 제외 1위)
                hi_all, hi = top_pair(high_rows)
                if not lo_all or not hi_all or not total:
                    print(f"  {dbcat}/{part}/{grade}: 상품 없음")
                    sv({"day": day, "part": part, "grade_f": grade, "total": 0})
                    continue
                if not lo or not hi:
                    print(f"[주의] {part}/{grade}: 맨 위 30건이 모두 명품이라 일반 상품 가격을 못 찾음 (건너뜀)")
                    continue
                if lo["price_kg"] > hi["price_kg"]:
                    print(f"[주의] {part}/{grade}: 정렬이 반대로 적용됨(최저>최고). 확인 필요")
                rec = {"day": day, "part": part, "grade_f": grade, "total": total, "pgrp": group,
                       "min_img": lo.get("img") if cfg.get("img") else None,
                       "min_name": lo.get("name") if cfg.get("img") else None,
                       "min_kg": lo["price_kg"], "min_goods": lo["goods_no"], "min_brand": lo["brand"], "min_grade": lo["grade"],
                       "max_kg": hi["price_kg"], "max_goods": hi["goods_no"], "max_brand": hi["brand"], "max_grade": hi["grade"],
                       "min_all_kg": lo_all["price_kg"], "max_all_kg": hi_all["price_kg"],
                       "min_origin": lo.get("origin"), "max_origin": hi.get("origin")}
                sv(rec)
                note = f"  (명품 포함 최고 {hi_all['price_kg']:,})" if hi_all["premium"] else ""
                print(f"  {dbcat}/{part}/{grade}: 최저 {lo['price_kg']:,} ({lo['brand']}) / 최고 {hi['price_kg']:,} ({hi['brand']})  [{total}건]{note}", flush=True)
                time.sleep(random.uniform(*DELAY))
        export_latest(con, day)                                  # 부위마다 중간 저장


def collect(show=False, resume=False, only=None, cats=None):
    from playwright.sync_api import sync_playwright
    day, con = date.today().isoformat(), sqlite3.connect(DB)
    init_db(con)
    import_history(con)                               # history.json 이 있으면 과거 기록 복원
    cats = cats or list(CATEGORIES)
    started = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not show)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.set_default_timeout(20000)
        for cat in cats:
            if cat not in CATEGORIES:
                print(f"[주의] 모르는 카테고리: {cat} (가능: {', '.join(CATEGORIES)})", file=sys.stderr)
                continue
            try:
                run_category(page, con, day, cat, CATEGORIES[cat], only, resume)
            except Exception as e:                       # 한 카테고리가 실패해도 다음 카테고리는 계속
                print(f"[실패] {cat} 카테고리 전체: {str(e)[:200]}", file=sys.stderr, flush=True)
                dump_debug(page, f"cat_{cat}")
        browser.close()
    n = export_latest(con, day)
    print(f"완료. latest.json {n}건 저장 ({int(time.time()-started)}초)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", help="저장한 HTML로 읽기 검증")
    ap.add_argument("--show", action="store_true", help="브라우저 창을 띄워서 실행(원인 확인용)")
    ap.add_argument("--resume", action="store_true", help="오늘 이미 받은 부위/등급은 건너뛰고 이어서 수집")
    ap.add_argument("--cat", help="세미콜론(;)으로 구분한 카테고리만 수집 (예: \"한우암소;육우거세\") — 기본은 전부")
    ap.add_argument("--parts", help="세미콜론(;)으로 구분한 부위만 수집 (예: \"안심;등심\")")
    a = ap.parse_args()
    if a.test:
        total, rows = parse_list(open(a.test, encoding="utf-8").read())
        print("총", total, "건 / 읽은 건수", len(rows))
        print("요약:", summarize(rows))
        print("첫 상품:", rows[0] if rows else None)
    else:
        only = [x.strip() for x in a.parts.split(";")] if a.parts else None
        cats = [x.strip() for x in a.cat.split(";")] if a.cat else None
        collect(show=a.show, resume=a.resume, only=only, cats=cats)
