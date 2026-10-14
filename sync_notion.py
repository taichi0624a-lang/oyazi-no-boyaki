"""
Notion 映画DB → movies_watched.json 同期スクリプト
GitHub Actions で自動実行。
"""
import requests
import json, os, sys, io, time, re

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


def overseas_poster(mid):
    """日本版を避けた海外ポスター（オリジナル言語→英語→テキストレス国際版）を返す。無ければ ''"""
    try:
        meta = requests.get(f"https://api.themoviedb.org/3/movie/{mid}?api_key={TMDB_API_KEY}", timeout=12).json()
        orig = meta.get("original_language", "") or ""
        d = requests.get(f"https://api.themoviedb.org/3/movie/{mid}/images?api_key={TMDB_API_KEY}", timeout=12).json()
        cands = [p for p in d.get("posters", []) if (p.get("iso_639_1") or "") != "ja"]
        if not cands:
            return ""
        def rank(p):
            l = p.get("iso_639_1") or ""
            pref = 4 if (l == orig and orig and orig != "ja") else 3 if l == "en" else 2 if l == "" else 1
            return (pref, p.get("vote_average", 0), p.get("vote_count", 0))
        cands.sort(key=rank, reverse=True)
        return cands[0].get("file_path", "") or ""
    except Exception:
        return ""


# ── 国名 英語→日本語 正規化 ──
COUNTRY_JP = {
    "United States of America": "アメリカ", "United States": "アメリカ", "USA": "アメリカ", "US": "アメリカ",
    "Japan": "日本", "United Kingdom": "イギリス", "UK": "イギリス", "South Korea": "韓国", "Korea": "韓国",
    "France": "フランス", "Germany": "ドイツ", "Italy": "イタリア", "Spain": "スペイン", "Hong Kong": "香港",
    "China": "中国", "Taiwan": "台湾", "Canada": "カナダ", "Australia": "オーストラリア", "Austria": "オーストリア",
    "Denmark": "デンマーク", "Sweden": "スウェーデン", "Norway": "ノルウェー", "Finland": "フィンランド",
    "Ireland": "アイルランド", "Netherlands": "オランダ", "Belgium": "ベルギー", "Switzerland": "スイス",
    "Russia": "ロシア", "India": "インド", "Mexico": "メキシコ", "Brazil": "ブラジル", "Argentina": "アルゼンチン",
    "Thailand": "タイ", "New Zealand": "ニュージーランド", "Poland": "ポーランド", "Czech Republic": "チェコ",
    "Czechoslovakia": "チェコスロバキア", "Slovakia": "スロバキア", "Iran": "イラン", "Israel": "イスラエル",
    "Turkey": "トルコ", "Greece": "ギリシャ", "Portugal": "ポルトガル", "Hungary": "ハンガリー",
    "Romania": "ルーマニア", "Indonesia": "インドネシア", "Philippines": "フィリピン", "Vietnam": "ベトナム",
    "Chile": "チリ", "Colombia": "コロンビア", "Iceland": "アイスランド", "Uruguay": "ウルグアイ",
    "Slovenia": "スロベニア", "Northern Ireland": "北アイルランド", "Singapore": "シンガポール",
    "Ukraine": "ウクライナ", "Georgia": "ジョージア", "Serbia": "セルビア", "Croatia": "クロアチア",
    "Bulgaria": "ブルガリア", "Luxembourg": "ルクセンブルク", "Qatar": "カタール", "South Africa": "南アフリカ",
    "Egypt": "エジプト", "Morocco": "モロッコ", "Lebanon": "レバノン", "Estonia": "エストニア",
    "Lithuania": "リトアニア", "Latvia": "ラトビア", "Cambodia": "カンボジア", "Malaysia": "マレーシア",
    "Peru": "ペルー", "Bolivia": "ボリビア", "Pakistan": "パキスタン", "Bhutan": "ブータン",
    "Senegal": "セネガル", "Kazakhstan": "カザフスタン", "Dominican Republic": "ドミニカ共和国",
    "Puerto Rico": "プエルトリコ",
}


def norm_country(c):
    if not c:
        return c
    out = []
    for p in re.split(r"[,/、]", c):
        p = p.strip()
        if p:
            out.append(COUNTRY_JP.get(p, p))
    seen = []
    for x in out:
        if x not in seen:
            seen.append(x)
    return ", ".join(seen)


# ── TMDB未紐付け(id=0)作品の自動照合 ──
_SUF = [r"4Kデジタルリマスター", r"4Kレストア版?", r"4K ?デジタル・?リマスター版?", r"デジタル・?リマスター版?",
        r"リマスター版?", r"レストア版?", r"修復版", r"無修正完全版", r"完全無修正完全版", r"ノーカット ?完全版",
        r"完全版", r"特別篇", r"特別版", r"ディレクターズ・?カット版?", r"ディレクター?ズカット版?",
        r"ノーカット", r"無修正", r"公開\d+周年記念版", r"\d+周年記念版", r"記念版", r"final cut",
        r"【[^】]*】", r"（原題）", r"\(原題\)", r"／REVENGE", r"4K ?"]
_ENG = {
    "コンクラーベ": "Conclave", "アノラ": "Anora", "ブルタリスト": "The Brutalist", "ヒット・マン": "Hit Man",
    "MONOS モノス": "Monos", "恋の罪": "Guilty of Romance", "べイビーわるきゅーれ": "Baby Assassins",
    "戦場のメリークリスマス 4K 修復版": "Merry Christmas Mr. Lawrence", "GUNDA／グンダ": "Gunda",
    "ウィッカーマン final cut": "The Wicker Man 1973",
}


def _clean_title(t):
    s = t
    for p in _SUF:
        s = re.sub(p, "", s)
    s = s.replace("　", " ").strip(" 　・-−ー！!")
    return re.sub(r"\s+", " ", s).strip()


def _norm(s):
    return re.sub(r"[\s　・:：!！?？\.，,\-–—]", "", (s or "")).lower()


def _tmdb_search(q, year=""):
    if not q:
        return []
    try:
        p = {"api_key": TMDB_API_KEY, "language": "ja-JP", "query": q}
        if year:
            p["year"] = year
        return requests.get("https://api.themoviedb.org/3/search/movie", params=p, timeout=12).json().get("results", [])
    except Exception:
        return []


def _choose(title, year):
    import difflib
    cq = _clean_title(title)
    eng = _ENG.get(title)
    cands = _tmdb_search(cq, year) + (_tmdb_search(cq) if year else [])
    if eng:
        cands = _tmdb_search(eng, year) + _tmdb_search(eng) + cands
    nq, neng = _norm(cq), _norm(eng or "")
    best, bs = None, -1
    for r in cands:
        rt, ro = r.get("title") or "", r.get("original_title") or ""
        sim = max(difflib.SequenceMatcher(None, nq, _norm(rt)).ratio(),
                  difflib.SequenceMatcher(None, nq, _norm(ro)).ratio())
        if neng:
            sim = max(sim, difflib.SequenceMatcher(None, neng, _norm(ro)).ratio())
        by = (r.get("release_date") or "")[:4]
        ym = 0
        if year and by:
            try:
                dy = abs(int(by) - int(year))
                ym = 1.0 if dy == 0 else (0.6 if dy == 1 else (0.3 if dy <= 2 else -0.3))
            except Exception:
                ym = 0
        score = sim + ym * 0.5
        if score > bs:
            bs, best = score, r
    return (best, bs) if (best and bs >= 0.5) else (None, bs)


def resolve_and_fill(movie):
    """id=0 の作品を TMDB で照合し、poster/監督/国/時間/ジャンル/あらすじ を補完"""
    best, _ = _choose(movie["title"], str(movie.get("year", "") or ""))
    if not best:
        return False
    try:
        d = requests.get(f"https://api.themoviedb.org/3/movie/{best['id']}",
                         params={"api_key": TMDB_API_KEY, "language": "ja-JP", "append_to_response": "credits"},
                         timeout=12).json()
    except Exception:
        return False
    if not d.get("poster_path"):
        return False
    director = ""
    for c in (d.get("credits", {}) or {}).get("crew", []):
        if c.get("job") == "Director":
            director = c.get("name", "")
            break
    movie["id"] = d["id"]
    movie["poster_path"] = d.get("poster_path", "") or ""
    movie["appDirector"] = movie.get("appDirector") or director
    movie["appCountry"] = movie.get("appCountry") or norm_country(", ".join(c.get("name", "") for c in d.get("production_countries", [])))
    movie["appRuntime"] = movie.get("appRuntime") or ((str(d.get("runtime")) + "分") if d.get("runtime") else "")
    movie["appGenre"] = movie.get("appGenre") or ", ".join(g.get("name", "") for g in d.get("genres", []))
    if not movie.get("year"):
        movie["year"] = (d.get("release_date") or "")[:4]
        movie["filmarksYear"] = movie["year"]
    movie["backdrop_path"] = d.get("backdrop_path", "") or ""
    movie["overview"] = d.get("overview", "") or ""
    movie["release_date"] = d.get("release_date", "") or ""
    movie["genre_ids"] = [g["id"] for g in d.get("genres", [])]
    return True


def notion_page_to_movie(page):
    """Notion ページ → movies_watched.json 形式に変換"""
    props = page["properties"]

    title     = "".join(t["plain_text"] for t in props["タイトル"]["title"])
    year      = str(int(props["製作年"]["number"])) if props["製作年"]["number"] else ""
    # 評価=0 は「観たい(towatch)」のマーカー。0.5〜5.0 or 空 は「観た(watched)」
    raw_score = props["評価"]["number"]
    is_towatch = (raw_score == 0)
    score     = str(raw_score) if (raw_score and raw_score > 0) else ""
    comment   = get_text(props["コメント"])
    url       = props["URL"]["url"] or ""
    director  = get_text(props["監督"])
    country   = norm_country(get_text(props["製作国"]))
    runtime   = get_text(props["上映時間"])
    genre     = get_text(props["ジャンル"])
    tmdb_id   = int(props["TMDb_ID"]["number"]) if props["TMDb_ID"]["number"] else 0
    poster    = get_text(props["poster_path"])
    # 「ベスト100」チェックボックス（THE CANON用）。列が無くても安全に False
    best100   = bool(props.get("ベスト100", {}).get("checkbox", False))
    # 追加日（Notionページ作成日）＝ Recently Added 並び用
    added     = (page.get("created_time") or "")[:10]

    return {
        "added":           added,
        "title":           title,
        "filmarksScore":   score,
        "filmarksComment": comment,
        "filmarksUrl":     url,
        "filmarksYear":    year,
        "year":            year,
        "appStatus":       "towatch" if is_towatch else "watched",
        "id":              tmdb_id,
        "poster_path":     poster,
        "appDirector":     director,
        "appCountry":      country,
        "appRuntime":      runtime,
        "appGenre":        genre,
        "best100":         best100,
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
            # 海外版ポスターを維持（既存jsonの poster を優先。日々の再取得を避ける）
            if prev.get("poster_path"):
                movie["poster_path"] = prev["poster_path"]
            # Notionにメタが無い作品は、補完済みjsonの値を引き継ぐ（翌日消さない）
            if not movie["id"] and prev.get("id"):
                movie["id"] = prev["id"]
                for k in ("poster_path", "appDirector", "appCountry", "appRuntime", "appGenre"):
                    if not movie.get(k) and prev.get(k):
                        movie[k] = prev[k]
                if not movie["year"] and prev.get("year"):
                    movie["year"] = prev["year"]
                    movie["filmarksYear"] = prev["year"]
        else:
            # 新規: id=0 なら TMDB 自動照合 → 補足情報取得
            print(f"  [新規] {title}", end=" ... ", flush=True)
            if not movie["id"]:
                if resolve_and_fill(movie):
                    print(f"自動照合OK(id={movie['id']})")
                else:
                    movie.update({"backdrop_path": "", "overview": "", "release_date": "", "genre_ids": []})
                    print("TMDbIDなし")
            else:
                extra = fetch_tmdb_extra(movie["id"])
                movie.update(extra)
                print("OK")
            # 新規は海外版ポスターを取得
            if movie["id"]:
                op = overseas_poster(movie["id"])
                if op:
                    movie["poster_path"] = op
            new_count += 1
            time.sleep(0.3)

        movies.append(movie)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完了: {len(movies)} 件 (新規 {new_count} 件) → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
