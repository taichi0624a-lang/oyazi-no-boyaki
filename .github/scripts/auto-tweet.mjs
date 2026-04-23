import { TwitterApi } from 'twitter-api-v2';

const FIREBASE_URL = 'https://ozi-blog-default-rtdb.asia-southeast1.firebasedatabase.app';

async function main() {
  // 最新の日記エントリを取得
  const res = await fetch(`${FIREBASE_URL}/diary.json`);
  const data = await res.json();
  if (!data) { console.log('記事なし'); return; }

  const entries = Object.values(data).sort((a, b) => new Date(b.date) - new Date(a.date));
  const latest = entries[0];

  // 前回ツイートした日時を取得
  const lastRes = await fetch(`${FIREBASE_URL}/twitter/lastTweetedDate.json`);
  const lastTweeted = await lastRes.json();

  if (lastTweeted === latest.date) {
    console.log('すでにツイート済み:', latest.title);
    return;
  }

  // ツイート投稿
  const client = new TwitterApi({
    appKey: process.env.TWITTER_API_KEY,
    appSecret: process.env.TWITTER_API_SECRET,
    accessToken: process.env.TWITTER_ACCESS_TOKEN,
    accessSecret: process.env.TWITTER_ACCESS_TOKEN_SECRET,
  });

  const excerpt = latest.body ? latest.body.replace(/\n/g, ' ').slice(0, 60) + '…' : '';
  const text = [
    `📝 新しい記事を投稿しました`,
    ``,
    `「${latest.title}」`,
    excerpt,
    ``,
    `https://kodomo-no-boyaki.com`,
  ].join('\n').slice(0, 280);

  await client.v2.tweet(text);
  console.log('ツイート完了:', latest.title);

  // 最終ツイート日時を更新
  await fetch(`${FIREBASE_URL}/twitter/lastTweetedDate.json`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(latest.date),
  });
}

main().catch(e => { console.error(e); process.exit(1); });
