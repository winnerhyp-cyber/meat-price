# 비밀번호로 감싼 index.html 에 '앱 설치' 정보를 넣어요 (manifest, 아이콘, 서비스 워커)
import sys
p = sys.argv[1] if len(sys.argv) > 1 else "index.html"
h = open(p, encoding="utf-8").read()
if "manifest.json" not in h:
    tags = ('<link rel="manifest" href="manifest.json">'
            '<meta name="theme-color" content="#8b2e2e">'
            '<link rel="apple-touch-icon" href="apple-touch-icon.png">'
            '<link rel="icon" href="icon-192.png">'
            '<meta name="apple-mobile-web-app-capable" content="yes">'
            '<meta name="mobile-web-app-capable" content="yes">'
            '<meta name="apple-mobile-web-app-title" content="단가표">'
            '<script>if("serviceWorker" in navigator)addEventListener("load",function(){navigator.serviceWorker.register("sw.js").catch(function(){})});</script>')
    h = h.replace("</head>", tags + "</head>", 1) if "</head>" in h else tags + h
    open(p, "w", encoding="utf-8").write(h)
    print("앱 설치 정보 넣음")
