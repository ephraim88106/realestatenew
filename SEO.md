# SEO 운영 가이드

## 한 줄 요약

**HTML 파일을 추가하거나 수정한 뒤 `python3 seo_fix.py` 를 실행하고 커밋한다.**

## seo_fix.py 가 하는 일

1. 모든 `*.html` 의 `<head>` 에 주입
   `canonical` · `robots` · `og:*` · `twitter:*` · Google Analytics · JSON-LD
   (기존 `description` 이 있으면 존중, 없을 때만 본문 첫 문단에서 생성)
2. 실제 파일을 스캔해 `sitemap.xml` 재생성
3. `robots.txt` 재생성 — 네이버 `Yeti`, 다음 `Daumoa` 명시 허용

주입 블록은 `<!-- SEO:BEGIN -->` ~ `<!-- SEO:END -->` 로 감싸여 있어
몇 번을 다시 돌려도 결과가 같다(멱등). 빈 줄이 쌓이지 않는다.

## ⚠️ URL 규칙

Cloudflare Pages 는 `.html` 확장자를 자동 제거한다.
`.html` 로 접근하면 **308 리다이렉트**가 걸리므로 canonical·사이트맵은
**확장자 없는 절대경로**를 쓴다.

```
O  https://realestatenew.pages.dev/article-name
X  https://realestatenew.pages.dev/article-name.html
```

한글 파일명은 URL 인코딩된다. 사이트맵 표준 요구사항이다.

## 도메인을 바꿀 때

`seo_fix.py` 상단의 `SITE` 상수 한 줄만 고치고 다시 실행하면
canonical · 사이트맵 · robots · OG URL 이 전부 따라온다.
단 `assets/og-default.png` 에 주소 텍스트가 그려져 있으므로 이미지도 새로 만들어야 한다.

## 검색엔진 등록

- Google Search Console — 사이트맵 제출: `https://realestatenew.pages.dev/sitemap.xml`
- 네이버 서치어드바이저 — 사이트 등록 후 **HTML 태그** 방식으로 소유확인
  (HTML 파일 방식은 위 308 리다이렉트 때문에 실패할 수 있다)
