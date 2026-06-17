"""
Notion 映画DB → movies_watched.json 同期スクリプト
GitHub Actions で自動実行。
"""
import requests
import json, os, sys, io, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

NOTION_TOKEN  = os.environ.get("NOTION_TOKEN", "")
DATABASE_ID   = "3829a1b78e3e801da338e50d65543814"
TMDB_API_KEY  = "c6dc0382ae920c2cb5143ff6a7ce97e6"
OUTPUT_FILE   = "movies_watched.json"

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


def fetch_all_notion_pages():
    """Notion DBの全ページをページネーションしながら取得"""
    pages = []
    cursor = None

    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor

        r = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers=NOTION_HEADERS,
            json=body,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        pages.extend(data.get("results", []))
        print(f"  取得: {len(pages)} 件...", flush=True)

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
        time.sleep(0.3)

    return pages


def get_text(prop):
    """rich_text プロパティからテキストを取得"""
    items = prop.get("rich_text", [])
    return "".join(t.get("plain_text", "") for t in items)


def fetch_tmdb_extra(tmdb_id):
    """TMDB IDから補足情報（backdrop, overview, release_date, genre_ids）を取得"""
    try:
        r = requests.get(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}"
            f"?api_key={TMDB_API_KEY}&language=ja-JP",
            timeout=10,
        )
        d = r.json()
        return {
            "backdrop_path": d.get("backdrop_path", "") or "",
            "overview":      d.get("overview", "") or "",
            "release_date":  d.get("release_date", "") or "",
            "genre_ids":     [g["id"] for g in d.get("genres", [])],
        }
    except Exception as e:
        print(f"TMDB失敗(id={tmdb_id}): {e}")
        return {"backdrop_path": "", "overview": "", "release_date": "", "genre_ids": []}


def notion_page_to_movie(page):
    """Notion ページ → movies_watched.json 形式に変換"""
    props = page["properties"]

    title     = "".join(t["plain_text"] for t in props["タイトル"]["title"])
    year      = str(int(props["製作年"]["number"])) if props["製作年"]["number"] else ""
    score     = str(props["評価"]["number"]) if props["評価"]["number"] else ""
    comment   = get_text(props["コメント"])
    url       = props["URL"]["url"] or ""
    director  = get_text(props["監督"])
    country   = get_text(props["製作国"])
    runtime   = get_text(props["上映時間"])
    genre     = get_text(props["ジャンル"])
    tmdb_id   = int(props["TMDb_ID"]["number"]) if props["TMDb_ID"]["number"] else 0
    poster    = get_text(props["poster_path"])

    return {
        "title":           title,
        "filmarksScore":   score,
        "filmarksComment": comment,
        "filmarksUrl":     url,
        "filmarksYear":    year,
        "year":            year,
        "appStatus":       "watched",
        "id":              tmdb_id,
        "poster_path":     poster,
        "appDirector":     director,
        "appCountry":      country,
        "appRuntime":      runtime,
        "appGenre":        genre,
    }


def main():
    print("=== Notion → movies_watched.json ===\n")

    if not NOTION_TOKEN:
        print("❌ NOTION_TOKEN が設定されていません")
        sys.exit(1)

    # 既存データ読み込み（TMDB補足情報を再利用するため）
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            try:
                for m in json.load(f):
                    existing[m["title"]] = m
                print(f"既存: {len(existing)} 件\n")
            except Exception:
                pass

    print("Notion からデータ取得中...")
    pages = fetch_all_notion_pages()
    print(f"\nNotion 合計: {len(pages)} 件\n")

    movies = []
    new_count = 0

    for page in pages:
        try:
            movie = notion_page_to_movie(page)
        except Exception as e:
            print(f"  スキップ: {e}")
            continue

        title = movie["title"]

        # 既存データからTMDB補足情報を再利用
        if title in existing:
            prev = existing[title]
            movie["backdrop_path"] = prev.get("backdrop_path", "")
            movie["overview"]      = prev.get("overview", "")
            movie["release_date"]  = prev.get("release_date", "")
            movie["genre_ids"]     = prev.get("genre_ids", [])
        else:
            # 新規: TMDBから補足情報を取得
            print(f"  [新規] {title}", end=" ... ", flush=True)
            if movie["id"]:
                extra = fetch_tmdb_extra(movie["id"])
                movie.update(extra)
                print("OK")
            else:
                movie.update({"backdrop_path": "", "overview": "", "release_date": "", "genre_ids": []})
                print("TMDbIDなし")
            new_count += 1
            time.sleep(0.3)

        movies.append(movie)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完了: {len(movies)} 件 (新規 {new_count} 件) → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
