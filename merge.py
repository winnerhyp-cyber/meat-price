# 카테고리별로 동시에 수집한 결과(parts/part-N/latest.json)를 하나로 합쳐요.
#  - _src/history.json : 전체 기록 (같은 날짜·카테고리·부위·등급은 새 값으로 덮어씀)
#  - _src/latest.json  : 가장 최근 날짜의 단가
# 각 작업은 자기 카테고리(cat.txt)의 값만 반영해요. (다른 카테고리의 예전 값이 새 값을 덮지 않게)
import glob, json, os, sys

HIST_KEEP = ["day", "category", "part", "grade_f", "total", "min_kg", "max_kg", "min_brand", "max_brand",
             "min_all_kg", "max_all_kg", "min_grade", "max_grade", "min_origin", "max_origin"]
K = lambda r: (r["day"], r.get("category") or "한우거세", r["part"], r["grade_f"])

def load(p, default):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return default

base_dir = sys.argv[1] if len(sys.argv) > 1 else "parts"
hist = load("_src/history.json", [])
old_latest = load("_src/latest.json", [])
H = {K(r): r for r in hist}
full = {K(r): r for r in old_latest}          # 상세 열까지 있는 최신 값

new_rows = 0
for d in sorted(glob.glob(os.path.join(base_dir, "*"))):
    try:
        cat = open(os.path.join(d, "cat.txt"), encoding="utf-8").read().strip()
    except Exception:
        continue
    rows = load(os.path.join(d, "latest.json"), [])
    mine = [r for r in rows if r.get("category") == cat or (r.get("category") or "").startswith(cat + "(")]
    for r in mine:
        H[K(r)] = {k: r.get(k) for k in HIST_KEEP}
        full[K(r)] = r
    new_rows += len(mine)
    print(f"{cat}: {len(mine)}건")

if new_rows:
    merged = sorted(H.values(), key=lambda r: (r["day"],))
    json.dump(merged, open("_src/history.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    last = max(r["day"] for r in merged)
    latest = [full.get(K(r), r) for r in merged if r["day"] == last and (r.get("total") or 0) > 0]
    json.dump(latest, open("_src/latest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"합치기 완료: 새 값 {new_rows}건, 최신({last}) {len(latest)}건, 전체 기록 {len(merged)}건")
else:
    print("새로 합칠 값이 없어요 (빠른 시험이거나 수집 실패). 기존 데이터로 화면만 다시 만들어요.")
