/* 임시 디버그용 - 확인 후 삭제 */
const MOLIT = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev";

export async function onRequest(context) {
  const { env } = context;

  if (!env.MOLIT_KEY) {
    return new Response(JSON.stringify({ error: "MOLIT_KEY 미설정" }), { headers: { "Content-Type": "application/json" } });
  }

  // 국토부 API 원본 XML 응답 확인
  const q = new URLSearchParams({ serviceKey: env.MOLIT_KEY, LAWD_CD: "28185", DEAL_YMD: "202606", numOfRows: "5", pageNo: "1" });
  const r = await fetch(`${MOLIT}?${q}`);
  const xml = await r.text();

  return new Response(JSON.stringify({
    has_MOLIT_KEY: true,
    key_length: env.MOLIT_KEY.length,
    http_status: r.status,
    raw_xml_preview: xml.slice(0, 800),  // 처음 800자만 표시
  }, null, 2), {
    headers: { "Content-Type": "application/json" }
  });
}
