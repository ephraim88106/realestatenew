#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish.py — 글을 추가한 뒤 딱 한 번 실행하면 되는 마무리 스크립트

    python3 publish.py

이게 하는 일 (순서대로):
  1) ads_fix.py  — 광고가 빠진 페이지에 애드핏 유닛 주입
  2) seo_fix.py  — canonical·og·robots 메타 주입, sitemap.xml·robots.txt 재생성
  3) 결과 요약 출력 (sitemap 개수 vs 실제 HTML 개수 대조)

왜 이 파일이 생겼나 (2026-08-03)
--------------------------------
두 가지 사고가 같은 원인으로 일어났다.

  · 광고 누락 — 자동 생성 템플릿에서 애드핏 스니펫이 빠진 채 수십 일 배포
  · sitemap 방치 — 7/25 이후 올린 글이 sitemap 에 한 건도 안 들어감
    (게다가 sangsang 은 sitemap URL 이 전부 리다이렉트되어 구글 색인 0개였음)

두 스크립트(ads_fix.py / seo_fix.py)는 원래부터 있었고 제대로 동작했다.
문제는 **아무도 안 돌렸다**는 것이다. 사람이 매번 기억해야 하는 단계는 반드시 빠진다.

그래서 기억할 명령을 하나로 줄였다. 글 올리고 `python3 publish.py` 한 번.
(GitHub Actions 가 켜져 있으면 푸시만 해도 서버에서 자동으로 돈다.)

주의
----
- 두 스크립트 모두 멱등(재실행 안전)이다. 몇 번을 돌려도 결과가 같다.
- 커밋·푸시는 하지 않는다. 이 스크립트를 돌린 뒤 직접 커밋하면 된다.
"""

import os, re, sys, glob, fnmatch, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP_DIRS = {".git", "node_modules", ".idx", ".vscode", ".github"}


# 색인·광고 대상이 아닌 파일 (약관류 + 검색엔진 소유확인 파일)
EXCLUDE_NAMES = {"404.html", "privacy.html", "terms.html", "policy.html"}
EXCLUDE_PATTERN = re.compile(r"^(naver|google|BingSiteAuth|yandex)[0-9a-zA-Z_-]*\.(html|xml)$", re.I)


def _load_ignore():
    """.publishignore — 점검에서 제외할 파일 패턴 (한 줄에 하나, glob 허용).

    '광고를 일부러 안 넣은 페이지'나 'robots.txt 로 막아둔 페이지'처럼
    의도적인 예외를 여기에 적어두면 매번 경고가 뜨지 않는다.
    # 로 시작하는 줄은 주석."""
    path = os.path.join(ROOT, ".publishignore")
    if not os.path.exists(path):
        return []
    pats = []
    for line in open(path, encoding="utf-8"):
        line = line.split("#")[0].strip()
        if line:
            pats.append(line)
    return pats


IGNORE = _load_ignore()


def is_excluded(rel):
    name = os.path.basename(rel)
    if name in EXCLUDE_NAMES or EXCLUDE_PATTERN.match(name):
        return True
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p) for p in IGNORE)


def run(script):
    path = os.path.join(ROOT, script)
    if not os.path.exists(path):
        print("  [건너뜀] %s 없음" % script)
        return True   # 없는 건 실패가 아니다
    r = subprocess.run([sys.executable, path], capture_output=True, text=True, cwd=ROOT)
    out = (r.stdout or "").strip() or (r.stderr or "").strip()
    for line in out.splitlines():
        print("  " + line)
    if r.returncode != 0:
        print("  ⚠️ %s 실패 (종료코드 %d)" % (script, r.returncode))
        return False
    return True


def all_html():
    out = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if f.endswith(".html"):
                out.append(os.path.relpath(os.path.join(dp, f), ROOT))
    return out


def audit():
    """sitemap 과 실제 파일, 광고 커버리지를 대조한다."""
    problems = []
    htmls = all_html()

    # 광고 커버리지
    noads = []
    for rel in htmls:
        try:
            s = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        except Exception:
            continue
        if "kakao_ad_area" not in s:
            noads.append(rel)

    # sitemap 대조
    sm = os.path.join(ROOT, "sitemap.xml")
    if os.path.exists(sm):
        from urllib.parse import unquote
        xml = open(sm, encoding="utf-8").read()
        locs = re.findall(r"<loc>([^<]+)</loc>", xml)
        bad_ext = [u for u in locs if u.endswith(".html")]
        bad_enc = [u for u in locs if re.search(r"[^\x00-\x7F]", u)]
        site = re.match(r"(https?://[^/]+)", locs[0]).group(1) if locs else ""
        insm = set()
        for u in locs:
            p = unquote(u.replace(site, "")).lstrip("/")
            insm.add("index.html" if p == "" else (p if p.endswith(".html") else p + ".html"))
        missing = sorted(set(htmls) - insm)

        print("\n[점검 결과]")
        print("  sitemap URL      : %d개" % len(locs))
        print("  실제 HTML 파일   : %d개" % len(htmls))
        print("  sitemap 미포함   : %d개" % len(missing))
        print("  .html 로 끝나는 URL (리다이렉트 유발): %d개" % len(bad_ext))
        print("  퍼센트 인코딩 안 된 URL              : %d개" % len(bad_enc))
        print("  광고 유닛 없는 페이지                : %d개" % len(noads))

        if bad_ext:
            problems.append(".html 로 끝나는 sitemap URL %d개 — 구글이 리다이렉트로 보고 색인 제외한다" % len(bad_ext))
        if bad_enc:
            problems.append("퍼센트 인코딩 안 된 sitemap URL %d개 — sitemap 규격 위반" % len(bad_enc))
        # 404 등 의도적 제외는 경고에서 뺀다
        real_missing = [m for m in missing if not is_excluded(m)]
        if real_missing:
            problems.append("sitemap 에 없는 페이지 %d개: %s" % (len(real_missing), ", ".join(real_missing[:3])))
    else:
        problems.append("sitemap.xml 이 없다")

    if noads:
        real = [n for n in noads if not is_excluded(n)]
        if real:
            problems.append("광고 유닛 없는 페이지 %d개: %s" % (len(real), ", ".join(real[:3])))

    return problems


def main():
    # 하위 스크립트가 죽었는데 "정상"이라고 보고하면 안 된다.
    # 2026-08-03: seo_fix.py 가 NameError 로 죽었는데도 점검이 통과해
    # 문제를 놓칠 뻔했다. 실패는 반드시 문제 목록에 올린다.
    failed = []

    print("[1/2] 광고 주입 — ads_fix.py")
    if not run("ads_fix.py"):
        failed.append("ads_fix.py")
    print("\n[2/2] SEO 정비 — seo_fix.py")
    if not run("seo_fix.py"):
        failed.append("seo_fix.py")

    problems = audit()
    for f in failed:
        problems.insert(0, "%s 가 실패했다 — 위 오류를 먼저 해결할 것" % f)

    print()
    if problems:
        print("⚠️  남은 문제 %d건 — 커밋 전에 확인할 것" % len(problems))
        for p in problems:
            print("   · " + p)
        return 1
    print("✅ 모두 정상. 이제 커밋·푸시하면 된다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
