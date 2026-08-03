#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEO 정비 스크립트 (재실행 안전 · 멱등)

하는 일
  1) 모든 *.html 의 <head> 에 SEO 메타 주입 (canonical / description / og / twitter / GA / JSON-LD)
  2) sitemap.xml 을 실제 파일 목록 기준으로 재생성
  3) robots.txt 재생성 (네이버 Yeti · 다음 Daumoa 명시 허용)

주의
  - Cloudflare Pages 가 .html 확장자를 자동 제거하므로 모든 URL은 **확장자 없는 절대경로**로 만든다.
    (.html 로 두면 308 리다이렉트가 발생해 색인에 불리하다)
  - 주입 블록은 <!-- SEO:BEGIN --> ~ <!-- SEO:END --> 로 감싸므로 재실행해도 결과가 동일하다.

사용:  python3 seo_fix.py
"""

import os, re, glob, json, html, datetime
from urllib.parse import quote

# ─────────────────────────── 사이트별 설정 ───────────────────────────
# 2026-08-03: pages.dev → 커스텀 도메인으로 전환.
# Search Console 실측 — 같은 날 제출한 사이트맵 중 커스텀 도메인만 즉시 "성공"으로
# 읽혔고(sangsang.ephseed.com: 252페이지 발견), pages.dev 는 "가져올 수 없음" 상태로
# 한 번도 크롤링되지 않았다. 사이트맵 파일 자체는 양쪽 다 정상이었다.
# *.pages.dev 는 누구나 무료로 서브도메인을 만드는 공용 호스트라 신뢰도가 0에서 시작한다.
# 기존 pages.dev 주소도 계속 서비스되지만 canonical 이 아래 도메인을 가리키므로
# 구글은 두 주소를 하나로 합쳐 평가한다.
SITE        = "https://realestatenew.ephseed.com"
SITE_NAME   = "인천 온라인 임장"
SITE_DESC   = "인천 지역 아파트·동네 정보를 온라인으로 미리 둘러보는 임장 서비스"
GA_ID       = "G-05H2B7ZS4E"          # 없으면 None
OG_IMAGE    = SITE + "/assets/og-default.png"
# 네이버 서치어드바이저 HTML 태그 방식 content 값 (웹마스터도구에서 발급)
NAVER_VERIFY = ""
DEAD_DOMAINS = []          # canonical 이 잘못 가리키던 죽은 도메인들
ARTICLE_RE  = re.compile(r"^(?!index)")   # 글로 취급할 파일명 패턴
# ────────────────────────────────────────────────────────────────────

ROOT = os.path.dirname(os.path.abspath(__file__))
TODAY = datetime.date.today().isoformat()
BEGIN, END = "<!-- SEO:BEGIN -->", "<!-- SEO:END -->"

# 색인 대상이 아닌 파일
EXCLUDE_NAMES = {"404.html"}
EXCLUDE_RE = re.compile(r"^(naver|google)[0-9a-f]{8,}\.html$")
SKIP_DIRS = {".git", "node_modules", "functions", ".github", ".firebase"}


def rel_paths():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if not fn.endswith(".html"):
                continue
            if fn in EXCLUDE_NAMES or EXCLUDE_RE.match(fn):
                continue
            out.append(os.path.relpath(os.path.join(dirpath, fn), ROOT).replace(os.sep, "/"))
    return sorted(out)


def clean_url(rel):
    if rel == "index.html":
        return SITE + "/"
    if rel.endswith("/index.html"):
        rel = rel[:-len("index.html")]
    elif rel.endswith(".html"):
        rel = rel[:-len(".html")]
    return SITE + "/" + quote(rel, safe="-_./~")


def strip_tags(s):
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def head_of(src):
    m = re.search(r"<head[^>]*>(.*?)</head>", src, flags=re.S | re.I)
    return m.group(1) if m else ""


def get_title(src):
    m = re.search(r"<title[^>]*>(.*?)</title>", src, flags=re.S | re.I)
    t = strip_tags(m.group(1)) if m else ""
    return t or SITE_NAME


def get_description(src):
    h = head_of(src)
    m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', h, flags=re.S | re.I)
    if m and m.group(1).strip():
        return strip_tags(m.group(1))[:300]
    body = re.sub(r"<head.*?</head>", " ", src, flags=re.S | re.I)
    for para in re.findall(r"<p[^>]*>(.*?)</p>", body, flags=re.S | re.I):
        t = strip_tags(para)
        if len(t) >= 30:
            return (t[:157] + "…") if len(t) > 158 else t
    for tag in ("h1", "h2"):
        m = re.search(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), body, flags=re.S | re.I)
        if m:
            t = strip_tags(m.group(1))
            if t:
                return t[:158]
    return (get_title(src) or SITE_DESC)[:158]


def lastmod_of(rel):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", rel)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            pass
    return TODAY


def is_article(rel):
    return bool(ARTICLE_RE.search(os.path.basename(rel)))


def esc(s):
    return html.escape(s, quote=True)


def build_block(rel, src):
    title, desc, url = get_title(src), get_description(src), clean_url(rel)
    h = head_of(src)
    parts = [BEGIN]

    if NAVER_VERIFY and rel == "index.html":
        parts.append('<meta name="naver-site-verification" content="%s">' % NAVER_VERIFY)

    if not re.search(r'<meta\s+name=["\']description["\']', h, flags=re.I):
        parts.append('<meta name="description" content="%s">' % esc(desc))

    parts += [
        '<link rel="canonical" href="%s">' % url,
        '<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">',
        '<meta property="og:type" content="%s">' % ("article" if is_article(rel) else "website"),
        '<meta property="og:site_name" content="%s">' % esc(SITE_NAME),
        '<meta property="og:title" content="%s">' % esc(title),
        '<meta property="og:description" content="%s">' % esc(desc),
        '<meta property="og:url" content="%s">' % url,
        '<meta property="og:locale" content="ko_KR">',
        '<meta property="og:image" content="%s">' % OG_IMAGE,
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:image" content="%s">' % OG_IMAGE,
    ]
    if is_article(rel):
        d = lastmod_of(rel)
        parts += ['<meta property="article:published_time" content="%sT09:00:00+09:00">' % d,
                  '<meta property="article:modified_time" content="%sT09:00:00+09:00">' % d]

    if GA_ID and GA_ID not in src:
        parts.append(
            '<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>'
            '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
            'gtag("js",new Date());gtag("config","%s");</script>' % (GA_ID, GA_ID))

    if "application/ld+json" not in h:
        org = {"@type": "Organization", "@id": SITE + "/#organization",
               "name": SITE_NAME, "url": SITE + "/"}
        site = {"@type": "WebSite", "@id": SITE + "/#website", "url": SITE + "/",
                "name": SITE_NAME, "description": SITE_DESC, "inLanguage": "ko-KR",
                "publisher": {"@id": SITE + "/#organization"}}
        node = {"@type": "Article" if is_article(rel) else "WebPage",
                "@id": url + "#page", "url": url,
                "headline" if is_article(rel) else "name": title,
                "description": desc, "inLanguage": "ko-KR", "image": OG_IMAGE,
                "isPartOf": {"@id": SITE + "/#website"}}
        if is_article(rel):
            d = lastmod_of(rel)
            node.update({"datePublished": d, "dateModified": d,
                         "author": {"@id": SITE + "/#organization"},
                         "publisher": {"@id": SITE + "/#organization"}})
        parts.append('<script type="application/ld+json">%s</script>'
                     % json.dumps({"@context": "https://schema.org", "@graph": [org, site, node]},
                                  ensure_ascii=False))

    parts.append(END)
    return "\n".join(parts)


def fix_file(rel):
    path = os.path.join(ROOT, rel)
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if "</head>" not in src.lower():
        return "head없음"

    for dead in DEAD_DOMAINS:
        src = src.replace("https://" + dead, SITE).replace("http://" + dead, SITE)

    src = re.sub(r"[ \t]*\n?" + re.escape(BEGIN) + r".*?" + re.escape(END) + r"[ \t]*\n?",
                 "", src, flags=re.S)

    def clean_head(m):
        h = m.group(0)
        h = re.sub(r'[ \t]*<link[^>]+rel=["\']canonical["\'][^>]*>[ \t]*\n?', "", h, flags=re.I)
        h = re.sub(r'[ \t]*<meta[^>]+property=["\']og:[^"\']*["\'][^>]*>[ \t]*\n?', "", h, flags=re.I)
        h = re.sub(r'[ \t]*<meta[^>]+name=["\']twitter:[^"\']*["\'][^>]*>[ \t]*\n?', "", h, flags=re.I)
        h = re.sub(r"\n{3,}", "\n\n", h)
        h = re.sub(r"[ \t\n]*</head>", "\n</head>", h, flags=re.I)
        return h
    src = re.sub(r"<head[^>]*>.*?</head>", clean_head, src, flags=re.S | re.I)

    block = build_block(rel, src)
    src = re.sub(r"[ \t\n]*</head>", "\n" + block + "\n</head>", src, count=1, flags=re.I)

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    return "ok"


def write_sitemap(rels):
    urls = []
    for rel in rels:
        pr = "1.0" if rel == "index.html" else ("0.8" if "/" not in rel else "0.7")
        urls.append("  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n"
                    "    <changefreq>weekly</changefreq>\n    <priority>%s</priority>\n  </url>"
                    % (clean_url(rel), lastmod_of(rel), pr))
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "\n".join(urls) + "\n</urlset>\n")
    return len(urls)


def write_robots():
    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write("""User-agent: *
Allow: /

# 네이버
User-agent: Yeti
Allow: /

# 다음(카카오)
User-agent: Daum
Allow: /

User-agent: Daumoa
Allow: /

# 구글
User-agent: Googlebot
Allow: /

User-agent: Googlebot-Image
Allow: /

# 빙
User-agent: Bingbot
Allow: /

Sitemap: %s/sitemap.xml
""" % SITE)


if __name__ == "__main__":
    rels = rel_paths()
    stats, ok_rels = {}, []
    for rel in rels:
        r = fix_file(rel)
        stats[r] = stats.get(r, 0) + 1
        if r == "ok":
            ok_rels.append(rel)
    n = write_sitemap(ok_rels)
    write_robots()
    print("메타 주입: %s" % ", ".join("%s %d개" % (k, v) for k, v in stats.items()))
    print("sitemap.xml: %d개 URL (%s)" % (n, SITE))
    print("robots.txt: 갱신 완료")
