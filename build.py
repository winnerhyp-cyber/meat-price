# 매일 자동 실행 때 쓰는 파일: 최신 데이터를 화면에 넣어서 plain.html 을 만들어요.
# (이 뒤에 staticrypt 가 plain.html 을 비밀번호로 암호화해서 index.html 이 됩니다)
import json, re

KEEP_DAYS = 60   # 화면에 넣는 최근 일수 (전체 기록은 _src/history.json 에 계속 쌓여요)

def dump(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

src = open("_src/app.html", encoding="utf-8").read()
latest = json.load(open("_src/latest.json", encoding="utf-8"))
hist = json.load(open("_src/history.json", encoding="utf-8"))
days = sorted({r["day"] for r in hist})
keep = set(days[-KEEP_DAYS:])
hist = [r for r in hist if r["day"] in keep]

src = re.sub(r"<script>window\.EMBED=.*?;</script>\n?", "", src, flags=re.S)
data = "<script>window.EMBED=%s;window.EMBED_HIST=%s;</script>\n" % (dump(latest), dump(hist))
marker = "<script>\nconst GRADES"
assert marker in src, "app.html 에서 삽입 위치를 못 찾았어요"
src = src.replace(marker, data + marker, 1)
open("plain.html", "w", encoding="utf-8").write(src)
print("plain.html 만듦: 최신 %d건, 기록 %d건 (%d일)" % (len(latest), len(hist), len(keep)))
