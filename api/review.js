// Vercel serverless: サイトから書いたレビュー(コメント＋評価)をNotion映画DBに書き込む。
// 必要: Vercel の環境変数 NOTION_TOKEN（GitHub Actionと同じ Notion internal integration token）。
const DB = '3829a1b78e3e801da338e50d65543814';
const SECRET = 'o24-secret-2026';

module.exports = async (req, res) => {
  if (req.method !== 'POST') { res.status(405).json({ ok: false, error: 'method' }); return; }

  const token = process.env.NOTION_TOKEN;
  if (!token) { res.status(200).json({ ok: false, error: 'no-token' }); return; }

  let body = req.body;
  if (typeof body === 'string') { try { body = JSON.parse(body); } catch (_) { body = {}; } }
  body = body || {};
  if (body.secret !== SECRET) { res.status(403).json({ ok: false, error: 'secret' }); return; }

  const H = {
    'Authorization': `Bearer ${token}`,
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json',
  };

  try {
    // 1) TMDb_ID で該当ページを検索
    let pageId = null;
    if (body.id) {
      const q = await fetch(`https://api.notion.com/v1/databases/${DB}/query`, {
        method: 'POST', headers: H,
        body: JSON.stringify({ filter: { property: 'TMDb_ID', number: { equals: Number(body.id) } }, page_size: 1 }),
      });
      const qd = await q.json();
      if (qd.results && qd.results[0]) pageId = qd.results[0].id;
    }
    // 2) 見つからなければタイトル検索でフォールバック
    if (!pageId && body.title) {
      const s = await fetch('https://api.notion.com/v1/search', {
        method: 'POST', headers: H,
        body: JSON.stringify({ query: body.title, page_size: 5 }),
      });
      const sd = await s.json();
      const hit = (sd.results || []).find(r => r.parent && r.parent.database_id &&
        r.parent.database_id.replace(/-/g, '') === DB);
      if (hit) pageId = hit.id;
    }
    if (!pageId) { res.status(200).json({ ok: false, error: 'not-found' }); return; }

    // 3) コメント＋評価を更新
    const props = {};
    if (body.comment != null && String(body.comment).length) {
      props['コメント'] = { rich_text: [{ text: { content: String(body.comment).slice(0, 1900) } }] };
    }
    const sc = parseFloat(body.score);
    if (sc > 0) props['評価'] = { number: sc };
    if (!Object.keys(props).length) { res.status(200).json({ ok: false, error: 'empty' }); return; }

    const p = await fetch(`https://api.notion.com/v1/pages/${pageId}`, {
      method: 'PATCH', headers: H, body: JSON.stringify({ properties: props }),
    });
    const pd = await p.json();
    res.status(200).json({ ok: pd && pd.object === 'page', pageId });
  } catch (e) {
    res.status(200).json({ ok: false, error: String(e) });
  }
};
