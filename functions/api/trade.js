/* ============================================================
 * Pages Function: /api/trade  ← 국토부 아파트 매매 실거래가 프록시
 * ------------------------------------------------------------
 * 같은 사이트 안(functions/api/trade.js)에서 도니 CORS 불필요.
 * 인증키는 코드에 넣지 말고 Pages 대시보드에 등록:
 *   프로젝트 › Settings › Environment variables › MOLIT_KEY (Encrypt)
 *   값 = data.go.kr "Decoding" 일반 인증키
 * 호출: /api/trade?LAWD_CD=28185&umd=송도동&months=6
 *       /api/trade?LAWD_CD=28185&DEAL_YMD=202606
 *       /api/trade?...&raw=1   (이상치 필터 끄기)
 * ============================================================ */

const MOLIT = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev";
const DEFAULT_LAWD = "28185";
const CACHE_TTL = 60 * 60 * 6;
const MAX_MONTHS = 12;

export async function onRequest(context) {
  const { request: req, env } = context;
  if (req.method === "OPTIONS")
    return new Response(null, { headers: cors() });

  const url = new URL(req.url);
  const lawd = (url.searchParams.get("LAWD_CD") || DEFAULT_LAWD).trim();
  const umd  = (url.searchParams.get("umd") || "").trim();      // "" => 시군구 전체
  const ymParam = url.searchParams.get("DEAL_YMD");
  const monthsParam = parseInt(url.searchParams.get("months") || "0", 10);
  const raw = url.searchParams.get("raw") === "1";

  const yms = ymParam ? [ymParam]
    : monthsList(Math.min(Math.max(monthsParam || 3, 1), MAX_MONTHS));

  const cache = caches.default;
  const cacheKey = new Request(url.toString(), req);
  const hit = await cache.match(cacheKey);
  if (hit) return hit;

  if (!env.MOLIT_KEY)
    return json({ error: "MOLIT_KEY 미설정 · Pages Settings › Environment variables 에 등록" }, 500);

  try {
    let items = [];
    for (const ym of yms) items = items.concat(await fetchMonth(env.MOLIT_KEY, lawd, ym));
    if (umd) items = items.filter(x => x.umd === umd);
    const cleaned = raw ? items : denoise(items);

    const res = json({
      region: { LAWD_CD: lawd, umd: umd || "전체" },
      months: yms, count: cleaned.length,
      summary: summarize(cleaned),
      items: cleaned,
    });
    res.headers.set("Cache-Control", `public, max-age=${CACHE_TTL}`);
    context.waitUntil(cache.put(cacheKey, res.clone()));
    return res;
  } catch (e) {
    return json({ error: String((e && e.message) || e) }, 502);
  }
}

async function fetchMonth(key, lawd, ym) {
  const q = new URLSearchParams({ serviceKey: key, LAWD_CD: lawd, DEAL_YMD: ym, numOfRows: "1000", pageNo: "1" });
  const r = await fetch(`${MOLIT}?${q}`, { cf: { cacheTtl: 21600, cacheEverything: true } });
  const xml = await r.text();
  if (/<returnReasonCode>/.test(xml) && !/<items>/.test(xml)) {
    const code = pick(xml, "returnReasonCode"), msg = pick(xml, "returnAuthMsg") || pick(xml, "errMsg");
    if (code && code !== "00" && code !== "000") throw new Error(`국토부 API 오류 ${code} ${msg}`.trim());
  }
  return parseItems(xml, ym);
}

function parseItems(xml, ym) {
  const out = [];
  for (const b of (xml.match(/<item>[\s\S]*?<\/item>/g) || [])) {
    const o = {};
    for (const m of b.matchAll(/<([^/>]+)>([\s\S]*?)<\/\1>/g)) o[m[1].trim()] = m[2].trim();
    const g = (...ks) => { for (const k of ks) if (o[k] != null && o[k] !== "") return o[k]; return ""; };
    const amt = Number(g("dealAmount", "거래금액").replace(/[,\s]/g, "")) || 0;
    const area = Number(g("excluUseAr", "전용면적")) || 0;
    const y = g("dealYear", "년") || ym.slice(0, 4);
    const mo = String(g("dealMonth", "월") || ym.slice(4)).padStart(2, "0");
    const d = String(g("dealDay", "일") || "").padStart(2, "0");
    const canceled = (g("cdealType", "해제여부") || "").toUpperCase() === "O" || !!g("cdealDay", "해제사유발생일");
    out.push({
      apt: g("aptNm", "아파트"), umd: g("umdNm", "법정동"), area, py: Math.round(area / 3.3058),
      amountEok: Math.round(amt / 100) / 100, floor: Number(g("floor", "층")) || null,
      buildYear: Number(g("buildYear", "건축년도")) || null, date: `${y}-${mo}-${d}`,
      dealType: g("dealingGubun", "거래유형") || "", canceled,
    });
  }
  return out;
}

function denoise(items) {
  const live = items.filter(x => !x.canceled && x.amountEok > 0);
  const groups = {};
  for (const x of live) (groups[`${x.apt}|${x.py}`] ||= []).push(x);
  const keep = [];
  for (const arr of Object.values(groups)) {
    const med = median(arr.map(x => x.amountEok));
    for (const x of arr) { const r = x.amountEok / med; if (r >= 0.6 && r <= 1.7) keep.push(x); }
  }
  return keep;
}

function summarize(items) {
  const s = {};
  for (const x of items) {
    const a = (s[x.apt] ||= {});
    const g = (a[x.py] ||= { latest: null, latestDate: "", max: 0, count: 0 });
    g.count++;
    if (x.amountEok > g.max) g.max = x.amountEok;
    if (x.date > g.latestDate) { g.latestDate = x.date; g.latest = x.amountEok; }
  }
  return s;
}

function monthsList(n) {
  const out = [], now = new Date();
  for (let i = 0; i < n; i++) { const dt = new Date(now.getFullYear(), now.getMonth() - i, 1); out.push(`${dt.getFullYear()}${String(dt.getMonth() + 1).padStart(2, "0")}`); }
  return out;
}
function median(a) { const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }
function pick(xml, t) { const m = xml.match(new RegExp(`<${t}>([\\s\\S]*?)</${t}>`)); return m ? m[1].trim() : ""; }
function cors() { return { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, OPTIONS", "Access-Control-Allow-Headers": "Content-Type" }; }
function json(obj, status = 200) { return new Response(JSON.stringify(obj, null, 2), { status, headers: { "Content-Type": "application/json; charset=utf-8", ...cors() } }); }
