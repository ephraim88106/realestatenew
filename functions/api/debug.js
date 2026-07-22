/* 임시 디버그용 - 확인 후 삭제 */
export async function onRequest(context) {
  const { env } = context;
  return new Response(JSON.stringify({
    has_MOLIT_KEY: !!env.MOLIT_KEY,
    key_length: env.MOLIT_KEY ? env.MOLIT_KEY.length : 0,
    env_keys: Object.keys(env),
  }, null, 2), {
    headers: { "Content-Type": "application/json" }
  });
}
