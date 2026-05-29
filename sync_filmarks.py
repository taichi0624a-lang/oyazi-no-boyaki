"""
Filmarks → movies_watched.json 同期スクリプト
GitHub Actions で自動実行。Google 認証不要。
"""
import requests
from bs4 import BeautifulSoup
import json, re, time, os, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

FILMARKS_USER = "sally0624"
TMDB_API_KEY  = "c6dc0382ae920c2cb5143ff6a7ce97e6"
OUTPUT_FILE   = "movies_watched.json"
HEADERS       = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ─── Filmarks スクレイプ ───────────────────────────────────────
def scrape_filmarks_all():
    """watched 全件をスクレイプ"""
    marks = []
    page  = 1

    while True:
        url = f"https://filmarks.com/users/{FILMARKS_USER}?page={page}"
        print(f"  Filmarks page {page}...", end=" ", flush=True)
        r = requests.get(url, headers=HEADERS, timeout=15)

        if r.status_code != 200:
            print(f"失敗 ({r.status_code})")
            break

        soup  = BeautifulSoup(r.text, "html.parser")
        cards = soup.select(".c-content-card")
        if not cards:
            print("記事なし → 終了")
            break

        page_marks = []
        for card in cards:
            title_el = card.select_one(".c-content-card__title a")
            if not title_el:
                continue

            span = title_el.select_one("span")
            year = ""
            if span:
                m = re.search(r"(\d{4})年", span.get_text())
                if m:
                    year = m.group(1)
                span.decompose()

            title     = title_el.get_text(strip=True)
            score_el  = card.select_one(".c-rating__score")
            score     = score_el.get_text(strip=True) if score_el else ""
            review_el = card.select_one(".c-content-card__review span")
            comment   = review_el.get_text(strip=True) if review_el else ""
            link      = ("https://filmarks.com" + title_el["href"]) if title_el.get("href") else ""

            page_marks.append({"title": title, "year": year,
                                "score": score, "comment": comment, "url": link})

        marks.extend(page_marks)
        print(f"{len(page_marks)} 件")

        # 次ページがなければ終了
        if not soup.select_one("a[rel='next'], .c2-pagination__next"):
            break
        page += 1
        time.sleep(0.8)

    return marks


# ─── TMDB メタデータ ──────────────────────────────────────────
def fetch_tmdb(title, year=""):
    try:
        q   = requests.utils.quote(title)
        url = (f"https://api.themoviedb.org/3/search/movie"
               f"?api_key={TMDB_API_KEY}&query={q}&language=ja-JP"
               + (f"&year={year}" if year else ""))
        results = requests.get(url, timeout=10).json().get("results", [])
        if not results:
            return None

        tmdb_id = results[0]["id"]
        d = requests.get(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}"
            f"?api_key={TMDB_API_KEY}&language=ja-JP&append_to_response=credits,images",
            timeout=10
        ).json()

        director = next(
            (c["name"] for c in d.get("credits", {}).get("crew", [])
             if c.get("job") == "Director"), "")
        country  = ", ".join(c.get("name","") for c in d.get("production_countries", []))
        runtime  = str(d.get("runtime","")) if d.get("runtime") else ""
        genres   = [g.get("name","") for g in d.get("genres", [])]
        genre    = ", ".join(genres)

        # ポスター（英語優先）
        poster_path   = d.get("poster_path","") or ""
        en_posters = [p["file_path"] for p in d.get("images",{}).get("posters",[])
                      if p.get("iso_639_1") in ("en", None)]
        if en_posters:
            poster_path = en_posters[0]

        return {
            "id":            tmdb_id,
            "poster_path":   poster_path,
            "backdrop_path": d.get("backdrop_path","") or "",
            "overview":      d.get("overview","") or "",
            "release_date":  d.get("release_date","") or "",
            "genre_ids":     [g["id"] for g in d.get("genres", [])],
            "appDirector":   director,
            "appCountry":    country,
            "appRuntime":    f"{runtime}分" if runtime else "",
            "appGenre":      genre,
        }
    except Exception as e:
        print(f"TMDB失敗: {e}")
        return None


# ─── メイン ──────────────────────────────────────────────────
def main():
    print("=== Filmarks → movies_watched.json ===\n")

    # 既存データ読み込み（差分更新用）
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            try:
                for m in json.load(f):
                    existing[m["title"]] = m
                print(f"既存: {len(existing)} 件\n")
            except Exception:
                pass

    # Filmarks スクレイプ
    print("Filmarks をスクレイプ中...")
    filmarks = scrape_filmarks_all()
    print(f"\nFilmarks 合計: {len(filmarks)} 件\n")

    all_movies = []
    new_count  = 0

    for fm in filmarks:
        title = fm["title"]

        if title in existing:
            # 既存データ再利用・Filmarks情報だけ更新
            m = dict(existing[title])
            m["filmarksScore"]   = fm["score"]
            m["filmarksComment"] = fm["comment"]
            m["filmarksUrl"]     = fm["url"]
            m["filmarksYear"]    = fm["year"]
            m["year"]            = fm["year"] or m.get("year","")
            m["appStatus"]       = "watched"
            all_movies.append(m)
        else:
            print(f"  [新規] {title}", end=" ... ", flush=True)
            tmdb = fetch_tmdb(title, fm["year"])
            time.sleep(0.4)

            base = {
                "title":          title,
                "filmarksScore":  fm["score"],
                "filmarksComment":fm["comment"],
                "filmarksUrl":    fm["url"],
                "filmarksYear":   fm["year"],
                "year":           fm["year"],
                "appStatus":      "watched",
            }

            if tmdb:
                base.update(tmdb)
                base["year"] = fm["year"] or tmdb.get("release_date","")[:4]
                print("OK")
            else:
                base.update({"id": 0, "poster_path":"", "backdrop_path":"",
                             "overview":"", "release_date":"", "genre_ids":[],
                             "appDirector":"", "appCountry":"",
                             "appRuntime":"", "appGenre":""})
                print("TMDBなし")

            all_movies.append(base)
            new_count += 1

    # 書き出し
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_movies, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完了: {len(all_movies)} 件 (新規 {new_count} 件) → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
