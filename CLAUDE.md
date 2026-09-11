# kodomo-no-boyaki — プロジェクトガイド

## サイト概要
個人ブログ `https://kodomo-no-boyaki.com`
文学的・ビンテージ感のある日記サイト。映画感想・日常のぼやきを投稿。

---

## デプロイフロー（必須）
```
編集 → git add → git commit → git push origin
→ Vercel が自動デプロイ（1〜2分で反映）
```
- **`firebase deploy` でも `netlify deploy` でもない**
- push 後は必ず変更ページの URL を表示する
- 本番 URL: `https://kodomo-no-boyaki.com`

---

## ファイル構成

| ファイル | 役割 |
|---|---|
| `index.html` | メインブログ（記事一覧・日記）|
| `archive.html` | 映画アーカイブ "drop off" |
| `videos.html` | 動画アーカイブ "BOOST" |
| `books.html` | 書籍アーカイブ |
| `about.html` | アバウトページ |
| `choco.html` | チョコの部屋（秘密） |
| `sync_notion.py` | Notion→movies_watched.json 同期スクリプト（GitHub Actions が毎朝実行）|
| `add_movie.py` | 映画登録スクリプト（Filmarks投稿＋TMDBメタ取得）Samanthaが呼び出す |
| `movies_watched.json` | 映画データ（GitHub Actions が自動更新）|

**触ってはいけないもの:**
- `C:\Users\taich\Desktop\o24-tools\` — Filmarks等Pythonツール用、ブログ編集では使わない

---

## GitHub
- リポジトリ: `https://github.com/taichi0624a-lang/oyazi-no-boyaki`
- デフォルトブランチ: `main`
- GitHub Actions: 毎日 JST 6:00 に `sync_notion.py` を自動実行（Notion→ブログ同期）

---

## デザイン言語

### フォント
- **Cormorant Garamond** — 見出し・数字・イタリック（文学的）
- **Space Mono** — ラベル・メタ情報（等幅・タイプライター風）
- **DM Sans** — 本文

### カラー（CSS変数）
```css
--bg:    #f5f2ec   /* クリーム背景 */
--paper: #faf9f5   /* 少し明るいクリーム */
--ink:   #0e0d0c   /* ほぼ黒 */
--red:   #aa1414   /* ボルドー赤（アクセント） */
--rule:  #ddd8ce   /* 罫線・ボーダー */
--dim:   #918d86   /* グレー（サブテキスト）*/
--warm:  #eae5dc   /* ホバー背景 */
```
ダークモード対応あり（`body.dark-mode`）。

### デザイン原則
- 文学的・ビンテージ感を崩さない
- 派手なアニメーションより「上品な静けさ」
- 余白を大事に

---

## データ構造

### ブログ記事（Firebase）
- Firebase Realtime Database: `ozi-blog-default-rtdb.asia-southeast1.firebasedatabase.app`
- `diary/` ノードに記事データ

### 映画アーカイブ（archive.html）
- 観た(WATCHED)・観たい(TOWATCH)とも **Notion 映画DB → sync_notion.py → `movies_watched.json`** に一本化（2026-09 Google Sheets卒業）
- **ステータス判定 = 「評価」列**：`評価=0` が **観たい(towatch)**、`0.5〜5.0 or 空` が **観た(watched)**（Notionにselect列を足せなかったための運用）
- archive.html は `appStatus` で watched/towatch を振り分け表示（Sheet読込は廃止）
- id=0（TMDB未紐付け）作品はクライアント側でタイトル再検索してポスター/予告を補完

---

## Python環境
- Anaconda: `C:/Users/taich/anaconda3/python.exe`
- スクリプト実行時はこのパスを使う

---

## 映画登録フロー（Samanthaへの指示）

ユーザーが「○○ 見た、評価4.0、コメントは〜」と言ったら:

1. **Filmarks 投稿**（`add_movie.py` を実行）
   ```
   C:/Users/taich/anaconda3/python.exe C:/Users/taich/Desktop/home/add_movie.py "タイトル" "スコア" "コメント"
   ```
   → 出力 JSON に `filmarks_url`, `tmdb_id`, `poster_path` など含まれる

2. **Notion に追加**（Notion MCP ツール `mcp__notion__API-post-page` を使用）
   - Database ID: `3829a1b78e3e801da338e50d65543814`
   - プロパティ: タイトル / 評価 / コメント / URL / 製作年 / 監督 / 製作国 / 上映時間 / ジャンル / TMDb_ID / poster_path

3. **ブログ反映**: 翌朝 JST 6:00 に GitHub Actions が自動実行（手動不要）

---

## よく使うコマンド
```bash
# デプロイ
cd C:/Users/taich/Desktop/home
git add .
git commit -m "変更内容"
git push origin

# 直前の変更を取り消す
git revert HEAD
git push origin

# 履歴確認
git log --oneline
```

---

## 注意事項
- GSAP は archive.html のみ使用。index.html では削除済み（CSS keyframes に移行）
- ローダーアニメーション（index.html）: フェードイン2s・保持1s・フェードアウト3s = 合計6s
- 記事番号 `No.XX` は発行順（oldest = No.01）
- 記事の並び順: 新着順（`b.id - a.id`）
- drop off の並び順: ランダム（デフォルト）
