# 매일 자동 실행 때 쓰는 파일: 최신 데이터를 화면에 넣어서 plain.html 을 만들어요.
# (입장코드를 쓸 때는 이 뒤에 staticrypt 가 plain.html 을 암호화해서 index.html 이 됩니다)
# 공개 중(open_days.txt 에 always)일 때는 검색에 잡히도록 부위별 시세 페이지(p/)와 sitemap.xml 도 만들어요.
import json, re, time, os, shutil, hashlib, html, datetime

KEEP_DAYS = 30   # 화면에 넣는 최근 일수 (전체 기록은 _src/history.json 에 계속 쌓여요)
SITE = "https://winnerhyp-cyber.github.io/meat-price/"

def dump(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

src = open("_src/app.html", encoding="utf-8").read()
latest = json.load(open("_src/latest.json", encoding="utf-8"))
hist_all = json.load(open("_src/history.json", encoding="utf-8"))
days = sorted({r["day"] for r in hist_all})
keep = set(days[-KEEP_DAYS:])
hist = [r for r in hist_all if r["day"] in keep]
last = days[-1] if days else None
SLIM = ["day", "category", "part", "grade_f", "total", "min_kg", "max_kg"]      # 지난 날짜는 용량 줄이려고 핵심 열만
hist = [r if r["day"] == last else {k: r.get(k) for k in SLIM} for r in hist]

# 검색엔진용 머리 정보 (설명·대표 이미지·소유확인 태그)
HEAD_EXTRA = ""
if os.path.exists("seo_meta.html"):
    HEAD_EXTRA = "".join(l.strip() for l in open("seo_meta.html", encoding="utf-8") if l.strip().startswith("<meta"))
DESC = "동원 금천미트 도매 단가표: 한우·한돈·수입 소고기·수입 돼지고기·닭·양·염소 Kg당 도매가를 매일 06시·18시 자동 수집. 삼겹살 도매가, 한우 등심 도매 시세, 전주 대비 변동을 한눈에."
main_head = ('<meta name="description" content="%s">' % html.escape(DESC) +
             '<meta name="keywords" content="고기 도매가,도매 시세,삼겹살 도매가,한우 도매가,한우 등심 도매 시세,수입육 도매가,금천미트,동원">' +
             '<link rel="canonical" href="%s">' % SITE +
             '<meta property="og:type" content="website"><meta property="og:title" content="동원 금천미트 도매 단가표 · 오늘 고기 도매 시세">' +
             '<meta property="og:description" content="%s">' % html.escape(DESC) +
             '<meta property="og:url" content="%s"><meta property="og:image" content="%sicon-512.png">' % (SITE, SITE) + HEAD_EXTRA)
src = src.replace("</head>", main_head + "</head>", 1)

src = re.sub(r"<script>window\.EMBED=.*?</script>\n?", "", src, flags=re.S)
ver = time.strftime("%Y%m%d%H%M%S")                                  # 새 단가 알림용 버전 표시
json.dump({"v": ver, "day": last}, open("version.json", "w"))
data = "<script>window.EMBED=%s;window.EMBED_HIST=%s;window.DATA_VER=%s;</script>\n" % (dump(latest), dump(hist), dump(ver))
marker = "<script>\n"          # 화면 코드가 시작하는 곳 바로 앞에 데이터를 넣어요
assert marker in src, "app.html 에서 삽입 위치를 못 찾았어요"
src = src.replace(marker, data + marker, 1)
open("plain.html", "w", encoding="utf-8").write(src)
print("plain.html 만듦: 최신 %d건, 기록 %d건 (%d일)" % (len(latest), len(hist), len(keep)))

# ───────────── 부위별 검색 페이지 ─────────────
is_open = os.path.exists("open_days.txt") and "always" in open("open_days.txt").read().split()
if not is_open:
    if os.path.isdir("p"):
        shutil.rmtree("p")
    open("sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>%s</loc></url></urlset>\n' % SITE)
    print("입장코드 사용 중이라 부위별 공개 페이지는 만들지 않아요")
    raise SystemExit(0)

CAT_ORDER = ["한우거세", "한우암소", "육우거세", "육우암소", "국내산 돈육", "수입냉장우육", "수입냉동우육", "수입냉장돈육", "수입냉동돈육", "계육", "양육", "염소", "세절육"]
HIDE = {"수입냉장우육(미국)", "수입냉장우육(호주)", "수입냉동우육(미국)", "수입냉동우육(호주)", "국내산돈육"}
CATN = {"한우거세": "한우(거세)", "한우암소": "한우(암소)", "육우거세": "육우(거세)", "육우암소": "육우(암소)", "국내산 돈육": "국내산 돼지고기(한돈)",
        "수입냉장우육": "수입 소고기(냉장)", "수입냉동우육": "수입 소고기(냉동)", "수입냉장돈육": "수입 돼지고기(냉장)", "수입냉동돈육": "수입 돼지고기(냉동)",
        "계육": "닭고기", "양육": "양고기", "염소": "염소고기", "세절육": "세절육(냉동)"}
KW = {"한우거세": "한우", "한우암소": "한우 암소", "육우거세": "육우", "육우암소": "육우 암소", "국내산 돈육": "한돈", "수입냉장우육": "수입 냉장 소고기",
      "수입냉동우육": "수입 냉동 소고기", "수입냉장돈육": "수입 냉장 돼지", "수입냉동돈육": "수입 냉동 돼지", "계육": "닭", "양육": "양고기", "염소": "염소", "세절육": "세절육"}
PORK = {"삼겹": "삼겹살", "목심": "목살(목심)", "앞다리": "앞다리살", "뒷다리": "뒷다리살", "항정": "항정살", "갈매기": "갈매기살", "삼겹(암)": "삼겹살(암)", "미박삼겹": "미박 삼겹살"}
GRADE_ORDER = ["1++", "1+", "1", "2", "3", "등외", "PR", "CAB", "CH(SRA)", "CH", "CH(SS)", "SEL", "GF", "PSA", "S", "A", "YP/GF", "전체"]
JOINURL = "https://www.ekcm.co.kr/me/join/memberjoin"
SHOP = "https://www.ekcm.co.kr/"
TELD = "010-3371-8953"
REF = "이현용"
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)
won = lambda n: "-" if n is None else format(int(round(n)), ",")
isC = lambda g: isinstance(g, str) and g.startswith("국가:")
gkey = lambda g: (GRADE_ORDER.index(g) if g in GRADE_ORDER else 50, g)
def pname(c, p):
    if c == "국내산 돈육":
        return PORK.get(p, p)
    return "차돌박이(냉동)" if p == "차돌박이" else p
def slug(c, p):
    return hashlib.md5((c + "|" + p).encode("utf-8")).hexdigest()[:10]
def glabel(g):
    return ("원산지 " + g[3:]) if isC(g) else ("전체" if g == "전체" else g + "등급" if re.match(r"^(1\+\+|1\+|1|2|3)$", g) else g)
def brand(r, w):
    b = (r.get(w + "_brand") or "")
    b = re.sub(r"\(.*\)$", "", b).strip()
    return " · ".join(x for x in [b, r.get(w + "_origin") or "", r.get(w + "_grade") or ""] if x)
def md(d):
    return "%d/%d" % (int(d[5:7]), int(d[8:10]))

rows = [r for r in latest if r.get("total", 0) > 0 and r.get("min_kg") and r.get("category") not in HIDE]
if not rows:
    print("부위별 페이지: 데이터 없음"); raise SystemExit(0)
today = max(r["day"] for r in rows)
rows = [r for r in rows if r["day"] == today]
# 기록: (종류, 부위, 등급) → {날짜: 행}
H = {}
cat_days = {}
for r in hist_all:
    if not r.get("min_kg") or r.get("category") in HIDE:
        continue
    H.setdefault((r["category"], r["part"], r["grade_f"]), {})[r["day"]] = r
    cat_days.setdefault(r["category"], {}).setdefault(r["day"], 0)
    cat_days[r["category"]][r["day"]] += 1
def prev_day(c):
    ds = cat_days.get(c, {})
    full, mx = [], 0
    for d in sorted(ds):
        if mx == 0 or ds[d] >= 0.6 * mx:
            full.append(d)
        mx = max(mx, ds[d])
    bf = [d for d in full if d < today]
    wk = (datetime.date.fromisoformat(today) - datetime.timedelta(days=7)).isoformat()
    c1 = [d for d in bf if d <= wk]
    if c1:
        return c1[-1], True
    return (bf[0], False) if bf else (None, False)

groups = {}
for r in rows:
    groups.setdefault((r["category"], r["part"]), []).append(r)
cats = [c for c in CAT_ORDER if any(k[0] == c for k in groups)] + sorted({k[0] for k in groups} - set(CAT_ORDER))
order = {c: [] for c in cats}
for r in rows:                                   # 수집 순서(화면과 비슷한 순서) 유지
    k = (r["category"], r["part"])
    if k[1] not in order[k[0]]:
        order[k[0]].append(k[1])

CSS = """*{box-sizing:border-box}body{margin:0;background:#f4f2ee;color:#1d2127;font:15px/1.6 Pretendard,-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif}
a{color:#8b2e2e}.w{max-width:860px;margin:0 auto;padding:16px}header.t{background:#8b2e2e;color:#fff}header.t .w{padding:14px 16px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
header.t a{color:#fff;text-decoration:none;font-weight:800}header.t span{opacity:.8;font-size:13px}.bc{font-size:13px;color:#6c717a;margin:4px 0 6px}.bc a{color:#6c717a}
h1{font-size:26px;line-height:1.3;margin:6px 0 4px}.d{color:#6c717a;font-size:13.5px;margin:0 0 14px}.box{background:#fff;border:1px solid #ebe7e0;border-radius:14px;padding:14px 16px;margin:0 0 14px}
.sum{display:flex;gap:18px;flex-wrap:wrap}.sum div{min-width:120px}.sum span{display:block;font-size:12.5px;color:#6c717a}.sum b{font-size:24px}.u{color:#d64545}.dn{color:#2f6fdb}
h2{font-size:18px;margin:0 0 10px}table{width:100%;border-collapse:collapse;font-size:14px}th{font-size:12px;color:#6c717a;text-align:left;border-bottom:2px solid #8b2e2e;padding:6px}
td{padding:8px 6px;border-bottom:1px solid #ebe7e0;vertical-align:top}td.r,th.r{text-align:right;white-space:nowrap}td small{display:block;color:#6c717a;font-size:11.5px}
.tw{overflow-x:auto}.cta{display:grid;gap:8px}.cta a{display:block;text-align:center;padding:13px;border-radius:12px;font-weight:800;text-decoration:none}
.cta .a1{background:#8b2e2e;color:#fff}.cta .a2{background:#fff;border:1.5px solid #8b2e2e}.ref{background:#f6e9e6;border-radius:12px;padding:10px 14px;font-size:14px}
.rel{display:flex;flex-wrap:wrap;gap:6px}.rel a{background:#fff;border:1px solid #ebe7e0;border-radius:999px;padding:5px 11px;font-size:13.5px;text-decoration:none;color:#1d2127}
.faq p{margin:0 0 8px}footer{color:#6c717a;font-size:12.5px;text-align:center;padding:20px 16px 30px}svg.sp{width:100%;height:90px}"""

def page(title, desc, canon, body, crumbs):
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList",
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(crumbs)]}
    return ('<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s</title><meta name="description" content="%s"><link rel="canonical" href="%s">'
            '<meta property="og:type" content="article"><meta property="og:title" content="%s"><meta property="og:description" content="%s"><meta property="og:url" content="%s">'
            '<meta property="og:image" content="%sicon-512.png"><link rel="icon" href="../icon-192.png">%s<style>%s</style>'
            '<script type="application/ld+json">%s</script></head><body>'
            '<header class="t"><div class="w"><a href="../?src=seo">동원 금천미트 도매 단가표</a><span>매일 06시·18시 자동 업데이트</span></div></header>'
            '<main class="w">%s</main><footer>금천미트 온라인몰 판매가를 모아 보여드려요 · 문의 %s (이현용 매니저)<br><a href="../?src=seo">전체 단가표 보기</a> · <a href="./">부위별 도매 시세 모음</a></footer></body></html>') % (
        E(title), E(desc), canon, E(title), E(desc), canon, SITE, HEAD_EXTRA, CSS, json.dumps(ld, ensure_ascii=False), body, TELD)

def spark(vals):
    vals = [v for v in vals if v]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    n = len(vals)
    pts = " ".join("%.1f,%.1f" % (i * 600 / (n - 1), 80 - (v - lo) / rng * 70) for i, v in enumerate(vals))
    return '<svg class="sp" viewBox="-4 -4 608 92" preserveAspectRatio="none" aria-hidden="true"><polyline points="%s" fill="none" stroke="#8b2e2e" stroke-width="2.5" vector-effect="non-scaling-stroke"/></svg>' % pts

if os.path.isdir("p"):
    shutil.rmtree("p")
os.makedirs("p")
urls = []
index_secs = []
for c in cats:
    pv, wkx = prev_day(c)
    cl = "전주 대비" if wkx else ("%s 대비" % md(pv) if pv else "전주 대비")
    links = []
    for p in order[c]:
        rs = sorted(groups[(c, p)], key=lambda r: (isC(r["grade_f"]), gkey(r["grade_f"])))
        main = [r for r in rs if not isC(r["grade_f"])] or rs
        lo = min(main, key=lambda r: r["min_kg"])
        hi = max(main, key=lambda r: r.get("max_kg") or r["min_kg"])
        name = pname(c, p)
        kw = KW.get(c, c)
        s = slug(c, p)
        # 전주 대비 (같은 등급끼리)
        def chg(r):
            if not pv:
                return None
            o = H.get((c, p, r["grade_f"]), {}).get(pv)
            return (r["min_kg"] - o["min_kg"]) / o["min_kg"] * 100 if o and o.get("min_kg") else None
        lch = chg(lo)
        ctxt = lambda x: "-" if x is None else ("– 변동 없음" if abs(x) < 0.05 else ("▲%.1f%%" % x if x > 0 else "▼%.1f%%" % abs(x)))
        ccls = lambda x: "" if x is None or abs(x) < 0.05 else ("u" if x > 0 else "dn")
        trs = "".join(
            '<tr><td>%s<small>상품 %d개</small></td><td class="r"><b>%s</b>원<small>%s</small></td><td class="r">%s원<small>%s</small></td><td class="r %s">%s</td></tr>' % (
                E(glabel(r["grade_f"])), r.get("total", 0), won(r["min_kg"]), E(brand(r, "min")), won(r.get("max_kg")), E(brand(r, "max")), ccls(chg(r)), ctxt(chg(r)))
            for r in rs)
        # 최근 30일 최저가 흐름 (등급 상관없이 그날 가장 싼 값)
        dmin = {}
        for r in main:
            for d, x in H.get((c, p, r["grade_f"]), {}).items():
                dmin[d] = min(dmin.get(d, 1e12), x["min_kg"])
        dmin[today] = min(dmin.get(today, 1e12), lo["min_kg"])
        ds = sorted(dmin)[-30:]
        hrows = "".join('<tr><td>%s</td><td class="r">%s원</td></tr>' % (d, won(dmin[d])) for d in reversed(ds[-10:]))
        grades_txt = ", ".join(glabel(r["grade_f"]) for r in rs[:6])
        title = "%s %s 도매가 · 오늘 도매 시세 (Kg당 가격) | 동원 금천미트" % (kw, name)
        desc = "%s 기준 %s %s Kg당 도매가 최저 %s원 ~ 최고 %s원 (%s). %s %s. 금천미트 온라인몰 단가를 매일 06시·18시 자동으로 모아요." % (
            today, CATN.get(c, c), name, won(lo["min_kg"]), won(hi.get("max_kg")), grades_txt, cl, ctxt(lch))
        rel = "".join('<a href="%s.html">%s</a>' % (slug(c, q), E(pname(c, q))) for q in order[c] if q != p)
        app_link = "../?src=seo#/c/" + E(c)
        body = (
            '<div class="bc"><a href="../?src=seo">홈</a> › <a href="./">부위별 도매 시세</a> › %s</div>' % E(CATN.get(c, c)) +
            '<h1>%s %s 도매가 · 도매 시세</h1><p class="d">기준일 %s · Kg당 원 · 금천미트 온라인몰 판매가 · %s</p>' % (E(kw), E(name), today, E(CATN.get(c, c))) +
            '<div class="box sum"><div><span>오늘 최저가</span><b>%s</b>원</div><div><span>오늘 최고가</span><b>%s</b>원</div><div><span>%s (최저가)</span><b class="%s">%s</b></div></div>' % (
                won(lo["min_kg"]), won(hi.get("max_kg")), cl, ccls(lch), ctxt(lch)) +
            '<div class="box"><h2>등급·원산지별 단가</h2><div class="tw"><table><thead><tr><th>구분</th><th class="r">최저가 (Kg)</th><th class="r">최고가 (Kg)</th><th class="r">%s</th></tr></thead><tbody>%s</tbody></table></div></div>' % (cl, trs) +
            ('<div class="box"><h2>최근 %d일 최저가 흐름</h2>%s<div class="tw"><table><thead><tr><th>날짜</th><th class="r">Kg당 최저가</th></tr></thead><tbody>%s</tbody></table></div></div>' % (len(ds), spark([dmin[d] for d in ds]), hrows) if len(ds) > 1 else "") +
            '<div class="box cta"><a class="a1" href="%s">📋 전체 단가표에서 %s 보기</a><a class="a2" href="%s" target="_blank" rel="noopener">🛒 금천미트에서 구매하기</a><a class="a2" href="%s" target="_blank" rel="noopener">👉 금천미트 회원가입</a>'
            '<div class="ref">🎁 금천미트 가입 때 <b>가입경로 상세</b>에 <b>%s</b>을 적으면 쿠폰을 드려요 · 가입 문의 <a href="tel:%s">%s</a></div></div>' % (app_link, E(name), SHOP, JOINURL, REF, TELD.replace("-", ""), TELD) +
            '<div class="box faq"><h2>자주 묻는 질문</h2><p><b>Q. 오늘 %s %s 도매가는 얼마인가요?</b><br>A. %s 기준 금천미트 온라인몰에서 Kg당 최저 %s원, 최고 %s원이에요. 가장 싼 상품은 %s 입니다.</p>'
            '<p><b>Q. 시세는 언제 바뀌나요?</b><br>A. 매일 아침 6시와 저녁 6시에 금천미트 판매가를 자동으로 다시 모아요. 실제 주문 가격은 주문 시점에 따라 달라질 수 있어요.</p></div>' % (
                E(kw), E(name), today, won(lo["min_kg"]), won(hi.get("max_kg")), E(brand(lo, "min") or glabel(lo["grade_f"]))) +
            ('<div class="box"><h2>%s 다른 부위 도매가</h2><div class="rel">%s</div></div>' % (E(CATN.get(c, c)), rel) if rel else ""))
        crumbs = [("홈", SITE), ("부위별 도매 시세", SITE + "p/"), (kw + " " + name, SITE + "p/%s.html" % s)]
        open("p/%s.html" % s, "w", encoding="utf-8").write(page(title, desc, SITE + "p/%s.html" % s, body, crumbs))
        urls.append(SITE + "p/%s.html" % s)
        links.append('<tr><td><a href="%s.html">%s %s 도매가</a></td><td class="r"><b>%s</b>원</td><td class="r %s">%s</td></tr>' % (s, E(kw), E(name), won(lo["min_kg"]), ccls(lch), ctxt(lch)))
    index_secs.append('<div class="box" id="%s"><h2>%s 도매 시세</h2><div class="tw"><table><thead><tr><th>부위</th><th class="r">Kg당 최저가</th><th class="r">%s</th></tr></thead><tbody>%s</tbody></table></div></div>' % (
        slug(c, ""), E(CATN.get(c, c)), cl, "".join(links)))
toc = '<div class="rel" style="margin:0 0 14px">%s</div>' % "".join('<a href="#%s">%s</a>' % (slug(c, ""), E(CATN.get(c, c))) for c in cats)
ibody = ('<div class="bc"><a href="../?src=seo">홈</a> › 부위별 도매 시세</div><h1>오늘 고기 도매 시세 · 부위별 Kg당 도매가</h1>'
         '<p class="d">기준일 %s · 한우·한돈·수입 소고기·수입 돼지고기·닭·양·염소 %d개 부위 · 금천미트 온라인몰 판매가를 매일 06시·18시 자동 수집</p>' % (today, len(urls)) +
         toc + "".join(index_secs) +
         '<div class="box cta"><a class="a1" href="../?src=seo">📋 전체 단가표 보기 (등급·브랜드별)</a><a class="a2" href="%s" target="_blank" rel="noopener">👉 금천미트 회원가입</a><div class="ref">🎁 가입경로 상세에 <b>%s</b> 입력 시 쿠폰 증정 · 문의 %s</div></div>' % (JOINURL, REF, TELD))
open("p/index.html", "w", encoding="utf-8").write(page("오늘 고기 도매 시세 · 삼겹살·한우 등심 등 부위별 Kg당 도매가 %s | 동원 금천미트" % md(today),
    "%s 기준 한우·한돈·수입육·닭·양·염소 부위별 Kg당 도매가 모음. 삼겹살 도매가, 한우 등심 도매 시세 등 %d개 부위를 매일 2번 업데이트." % (today, len(urls)),
    SITE + "p/", ibody, [("홈", SITE), ("부위별 도매 시세", SITE + "p/")]))
sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for u, pr in [(SITE, "1.0"), (SITE + "p/", "0.9")] + [(u, "0.7") for u in urls]:
    sm.append("<url><loc>%s</loc><lastmod>%s</lastmod><changefreq>daily</changefreq><priority>%s</priority></url>" % (u, today, pr))
sm.append("</urlset>")
open("sitemap.xml", "w", encoding="utf-8").write("\n".join(sm) + "\n")
print("부위별 페이지 %d개 + 목록 + sitemap.xml 만듦" % len(urls))
