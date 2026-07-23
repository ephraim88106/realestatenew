/* ============================================================
 * Pages Function: /api/board  ← 동별 자유게시판 (익명 + 비밀번호)
 * ------------------------------------------------------------
 * D1 바인딩 필요: Cloudflare Pages 대시보드 › Settings › Bindings ›
 *   Add › D1 database bindings › Variable name = DB, Database = realestatenew-board
 * 호출:
 *   GET    /api/board?dong=songdo&page=1        (목록, 20개씩)
 *   GET    /api/board?dong=songdo&id=12          (상세, 조회수 +1)
 *   POST   /api/board                            (작성) body: {dong,title,author,password,content,website}
 *   PUT    /api/board?id=12                       (수정) body: {password,title,content}
 *   DELETE /api/board?id=12                       (삭제) body: {password}
 * ============================================================ */

const PAGE_SIZE = 20;

export async function onRequestOptions() {
  return new Response(null, { headers: cors() });
}

export async function onRequestGet(context) {
  const { request, env } = context;
  if (!env.DB) return json({ error: "DB 바인딩 미설정 · Pages Settings › Bindings 에 D1 등록 필요" }, 500);
  const url = new URL(request.url);
  const dong = (url.searchParams.get("dong") || "").trim();
  const id = url.searchParams.get("id");
  if (!dong) return json({ error: "dong 파라미터 필요" }, 400);

  try {
    if (id) {
      const post = await env.DB.prepare(
        "SELECT id,dong,title,author,content,views,created_at FROM posts WHERE id=?1 AND dong=?2"
      ).bind(id, dong).first();
      if (!post) return json({ error: "글을 찾을 수 없어요" }, 404);
      await env.DB.prepare("UPDATE posts SET views=views+1 WHERE id=?1").bind(id).run();
      post.views += 1;
      return json({ post });
    }
    const page = Math.max(1, parseInt(url.searchParams.get("page") || "1", 10));
    const offset = (page - 1) * PAGE_SIZE;
    const { results } = await env.DB.prepare(
      "SELECT id,title,author,views,created_at FROM posts WHERE dong=?1 ORDER BY id DESC LIMIT ?2 OFFSET ?3"
    ).bind(dong, PAGE_SIZE, offset).all();
    const total = await env.DB.prepare("SELECT COUNT(*) AS c FROM posts WHERE dong=?1").bind(dong).first();
    return json({ posts: results, page, total: total.c, pageSize: PAGE_SIZE });
  } catch (e) {
    return json({ error: String((e && e.message) || e) }, 500);
  }
}

export async function onRequestPost(context) {
  const { request, env } = context;
  if (!env.DB) return json({ error: "DB 바인딩 미설정 · Pages Settings › Bindings 에 D1 등록 필요" }, 500);
  let body;
  try { body = await request.json(); } catch { return json({ error: "잘못된 요청" }, 400); }

  // 허니팟: 봇은 보통 숨겨진 필드까지 채움
  if (body.website) return json({ ok: true }); // 조용히 무시(스팸 성공한 척)

  const dong = String(body.dong || "").trim();
  const title = String(body.title || "").trim();
  const author = String(body.author || "").trim();
  const password = String(body.password || "");
  const content = String(body.content || "").trim();

  if (!dong) return json({ error: "동 정보가 없어요" }, 400);
  if (!title || title.length > 100) return json({ error: "제목은 1~100자로 입력해주세요" }, 400);
  if (!author || author.length > 20) return json({ error: "닉네임은 1~20자로 입력해주세요" }, 400);
  if (!password || password.length < 4 || password.length > 30) return json({ error: "비밀번호는 4~30자로 입력해주세요" }, 400);
  if (!content || content.length > 4000) return json({ error: "내용은 1~4000자로 입력해주세요" }, 400);

  try {
    const { hash, salt } = await hashPassword(password);
    const now = new Date().toISOString();
    const res = await env.DB.prepare(
      "INSERT INTO posts (dong,title,author,content,pw_hash,pw_salt,views,created_at) VALUES (?1,?2,?3,?4,?5,?6,0,?7)"
    ).bind(dong, title, author, content, hash, salt, now).run();
    return json({ ok: true, id: res.meta.last_row_id });
  } catch (e) {
    return json({ error: String((e && e.message) || e) }, 500);
  }
}

export async function onRequestPut(context) {
  const { request, env } = context;
  if (!env.DB) return json({ error: "DB 바인딩 미설정" }, 500);
  const url = new URL(request.url);
  const id = url.searchParams.get("id");
  if (!id) return json({ error: "id 파라미터 필요" }, 400);
  let body;
  try { body = await request.json(); } catch { return json({ error: "잘못된 요청" }, 400); }

  const title = String(body.title || "").trim();
  const content = String(body.content || "").trim();
  if (!title || title.length > 100) return json({ error: "제목은 1~100자로 입력해주세요" }, 400);
  if (!content || content.length > 4000) return json({ error: "내용은 1~4000자로 입력해주세요" }, 400);

  try {
    const row = await env.DB.prepare("SELECT pw_hash,pw_salt FROM posts WHERE id=?1").bind(id).first();
    if (!row) return json({ error: "글을 찾을 수 없어요" }, 404);
    const ok = await verifyPassword(String(body.password || ""), row.pw_hash, row.pw_salt);
    if (!ok) return json({ error: "비밀번호가 일치하지 않아요" }, 403);
    await env.DB.prepare("UPDATE posts SET title=?1, content=?2 WHERE id=?3").bind(title, content, id).run();
    return json({ ok: true });
  } catch (e) {
    return json({ error: String((e && e.message) || e) }, 500);
  }
}

export async function onRequestDelete(context) {
  const { request, env } = context;
  if (!env.DB) return json({ error: "DB 바인딩 미설정" }, 500);
  const url = new URL(request.url);
  const id = url.searchParams.get("id");
  if (!id) return json({ error: "id 파라미터 필요" }, 400);
  let body;
  try { body = await request.json(); } catch { body = {}; }

  try {
    const row = await env.DB.prepare("SELECT pw_hash,pw_salt FROM posts WHERE id=?1").bind(id).first();
    if (!row) return json({ error: "글을 찾을 수 없어요" }, 404);
    const ok = await verifyPassword(String(body.password || ""), row.pw_hash, row.pw_salt);
    if (!ok) return json({ error: "비밀번호가 일치하지 않아요" }, 403);
    await env.DB.prepare("DELETE FROM posts WHERE id=?1").bind(id).run();
    return json({ ok: true });
  } catch (e) {
    return json({ error: String((e && e.message) || e) }, 500);
  }
}

/* ---------- 비밀번호 해시 (Web Crypto, salt+SHA-256) ---------- */
async function hashPassword(password) {
  const salt = bufToHex(crypto.getRandomValues(new Uint8Array(16)));
  const hash = await sha256Hex(salt + password);
  return { hash, salt };
}
async function verifyPassword(password, hash, salt) {
  const check = await sha256Hex(salt + password);
  return check === hash;
}
async function sha256Hex(str) {
  const data = new TextEncoder().encode(str);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return bufToHex(digest);
}
function bufToHex(buf) {
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
}

function cors() { return { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS", "Access-Control-Allow-Headers": "Content-Type" }; }
function json(obj, status = 200) { return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json; charset=utf-8", ...cors() } }); }
