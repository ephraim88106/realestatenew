#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ads_fix.py — 카카오 애드핏 광고 스니펫 자동 주입 (재실행 안전 · 멱등)

왜 이 파일이 생겼나 (2026-08-03)
--------------------------------
전수 조사 결과 이 사이트의 상당수 페이지에 애드핏 광고가 통째로 빠져 있었다.
자동 생성 템플릿에서 스니펫이 누락된 채 배포가 반복된 것이 원인이다.
검색 유입이 몰리는 최신 글들이 그동안 무수익 상태였다.

사람이 매번 스니펫을 복사해 넣는 방식은 또 빠진다. 그래서 seo_fix.py 와
같은 방식으로 스크립트가 강제 주입하도록 만들었다.

사용법
------
    python3 ads_fix.py            # 누락분 주입
    python3 ads_fix.py --check    # 주입 없이 현황만 출력 (누락 시 종료코드 1)

주의
----
- 이미 kakao_ad_area 가 있는 파일은 건드리지 않는다 (멱등).
- <body> 가 정확히 1개가 아닌 파일은 안전을 위해 건너뛴다.
- 광고를 넣지 않을 페이지는 EXCLUDE 에 추가한다.
"""

import os, sys, glob

ROOT = os.path.dirname(os.path.abspath(__file__))

# 애드핏 광고 유닛 ID — 애드핏 콘솔에서 발급받은 이 사이트 전용 값
UNIT_TOP = "DAN-15Sw8np6dK9Kb4qK"    # 728x90 상단 배너
UNIT_SIDE = "DAN-lA36Isu0uoRExK8L"   # 160x600 우측 고정

# 새 도메인(*.ephseed.com) 전용 유닛 (2026-08-03 발급)
# 애드핏 매체는 도메인 단위로 등록된다. 위의 옛 유닛은 *.pages.dev 매체에
# 묶여 있어 새 도메인에서는 채워지지 않는다. 그래서 별도로 발급받았다.
UNIT_NEW = "DAN-KfZrU6n7Rgbm3mYu"
UNIT_NEW_W = 320
UNIT_NEW_H = 50

# 광고를 넣지 않을 페이지
EXCLUDE = {
    "404.html",
    "privacy.html",
    "terms.html",
    "policy.html",
}

AD_BLOCK = '''
<!-- ============================================= -->
<!-- 카카오 애드핏 광고 — ads_fix.py 자동 주입      -->
<!-- 직접 지우지 말 것. 지우면 그 페이지는 무수익.   -->
<!-- ============================================= -->
<div style="display:flex;justify-content:center;margin:12px 0;overflow:hidden;max-width:100%;">
<ins class="kakao_ad_area" style="display:none;"
data-ad-unit="__UNIT_TOP__"
data-ad-width="728"
data-ad-height="90"></ins>
</div>
<div class="kakao-right-fixed" style="position:fixed;top:100px;right:10px;z-index:1000;">
<ins class="kakao_ad_area" style="display:none;"
data-ad-unit="__UNIT_SIDE__"
data-ad-width="160"
data-ad-height="600"></ins>
</div>
<style>@media (max-width:1200px){.kakao-right-fixed{display:none !important;}}</style>
<!-- 새 도메인 전용 유닛 -->
<div class="kakao-ad-lead" style="display:flex;justify-content:center;align-items:center;margin:14px auto;max-width:100%;overflow:hidden;">
<ins class="kakao_ad_area" style="display:none;"
data-ad-unit="__UNIT_NEW__"
data-ad-width="__UNIT_NEW_W__"
data-ad-height="__UNIT_NEW_H__"></ins>
</div>
<style>
/* 728x90 은 모바일 화면에 들어가지 않는다. 가로 넘침·미노출 방지 */
@media (max-width:767px){
  ins.kakao_ad_area[data-ad-width="728"]{display:none !important;}
  .fixed-top-ad{display:none !important;}
}
</style>
<script type="text/javascript" src="//t1.kakaocdn.net/kas/static/ba.min.js" async></script>
'''.replace('__UNIT_TOP__', UNIT_TOP).replace('__UNIT_SIDE__', UNIT_SIDE).replace('__UNIT_NEW__', UNIT_NEW).replace('__UNIT_NEW_W__', str(UNIT_NEW_W)).replace('__UNIT_NEW_H__', str(UNIT_NEW_H))


def all_html():
    """하위 디렉터리까지 포함한 모든 html (.git 제외)"""
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", ".idx", ".vscode", ".github")]
        for fn in filenames:
            if fn.endswith(".html"):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def inject(path, dry=False):
    """반환값: 'ok' | 'already' | 'skip:<사유>'"""
    with open(path, encoding="utf-8") as f:
        src = f.read()

    if "kakao_ad_area" in src:
        return "already"
    if src.count("<body>") != 1:
        return "skip:body 태그가 1개가 아님"

    new = src.replace("<body>", "<body>" + AD_BLOCK, 1)

    # CSS 선택자에도 kakao_ad_area 문자열이 들어가므로 <ins 태그만 센다
    if new.count('<ins class="kakao_ad_area"') != 3 or new.count("ba.min.js") != 1:
        return "skip:삽입 검증 실패"

    if not dry:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
    return "ok"


def main():
    dry = "--check" in sys.argv
    targets = [p for p in all_html() if os.path.basename(p) not in EXCLUDE]

    stats, injected, skipped = {}, [], []
    for p in targets:
        r = inject(p, dry=dry)
        stats[r.split(":")[0]] = stats.get(r.split(":")[0], 0) + 1
        rel = os.path.relpath(p, ROOT)
        if r == "ok":
            injected.append(rel)
        elif r.startswith("skip"):
            skipped.append((rel, r.split(":", 1)[1]))

    print("애드핏 %s: 대상 %d개 / 이미 있음 %d개 / 신규 %d개 / 건너뜀 %d개"
          % ("검사만" if dry else "주입", len(targets),
             stats.get("already", 0), stats.get("ok", 0), stats.get("skip", 0)))

    if injected:
        print("  신규 주입:")
        for f in injected[:15]:
            print("    -", f)
        if len(injected) > 15:
            print("    ... 외 %d개" % (len(injected) - 15))

    if skipped:
        print("  ⚠️ 건너뜀 (수동 확인 필요):")
        for f, why in skipped:
            print("    -", f, "—", why)

    return 1 if (dry and stats.get("ok", 0) > 0) else 0


if __name__ == "__main__":
    sys.exit(main())
