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
| `sync_filmarks.py` | Filmarks→movies_watched.json 同期スクリプト |
| `movies_watched.json` | 映画データ（GitHub Actions が自動更新）|

**触ってはいけないもの:**
- `C:\Users\taich\Desktop\o24-tools\` — Filmarks等Pythonツール用、ブログ編集では使わない

---

## GitHub
- リポジトリ: `https://github.com/taichi0624a-lang/oyazi-no-boyaki`
- デフォルトブランチ: `main`
- GitHub Actions: 毎日 JST 6:00 に `sync_filmarks.py` を自動実行

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
- `movies_watched.json` から読み込み（Filmarks同期データ）
- フォールバック: Google Sheets CSV
- TOWATCH リストは引き続き Google Sheets から読み込み

---

## Python環境
- Anaconda: `C:/Users/taich/anaconda3/python.exe`
- スクリプト実行時はこのパスを使う

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
