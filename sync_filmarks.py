"""
Filmarks → Google Sheets 差分同期スクリプト
新しく鑑賞した映画だけをシートに追記する（TMDB メタデータ付き）
"""

import requests
from bs4 import BeautifulSoup
import json, os, re, time, sys

from google.oauth2 import service_account
from googleapiclient.discovery import build

# ===== 設定 =====
FILMARKS_USER  = "sally0624"
SPREADSHEET_ID = "1Kqff4ogYLk6L5W-vIby1CijrOmCxLF1_axpZaWZNr80"
SHEET_NAME     = "シート1"
TMDB_API_KEY   = "c6dc0382ae920c2cb5143ff6a7ce97e6"
SCOPES         = ["https://www.googleapis.com/auth/spreadsheets"]
HEADERS        = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
MAX_PAGES      = 5  # 最大何ページまでチェックするか

# ===== Google Sheets 接続 =====
def get_sheets_service():
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sa_json:
        raise RuntimeError("環境変数 GOOGLE_SERVICE_ACCOUNT_JSON が設定されていません")
    info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)

def get_existing_titles(service):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A2:A"
    ).execute()
    rows = result.get("values", [])
    return set(r[0].strip() for r in rows if r)

def append_to_sheet(service, rows):
    if not rows:
        return 0
    result = service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows}
    ).execute()
    return result.get("updates", {}).get("updatedRows", 0)

# ===== Filmarks スクレイプ =====
def scrape_filmarks_page(page_num):
    url = f"https://filmarks.com/users/{FILMARKS_USER}?page={page_num}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    if r.status_code != 200:
        print(f"  ページ {page_num} 取得失敗: {r.status_code}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    marks = []

    for card in soup.select(".c-content-card"):
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
        title = title_el.get_text(strip=True)

        score_el  = card.select_one(".c-rating__score")
        score     = score_el.get_text(strip=True) if score_el else ""

        review_el = card.select_one(".c-content-card__review span")
        comment   = review_el.get_text(strip=True) if review_el else ""

        link = ""
        if title_el.get("href"):
            link = "https://filmarks.com" + title_el["href"]

        marks.append({"title": title, "year": year, "score": score, "comment": comment, "url": link})

    return marks

# ===== TMDB メタデータ取得 =====
def fetch_tmdb_metadata(title, year=""):
    try:
        q = requests.utils.quote(title)
        url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={q}&language=ja-JP"
        if year:
            url += f"&year={year}"

        r = requests.get(url, timeout=10)
        results = r.json().get("results", [])
        if not results:
            return {}

        tmdb_id = results[0]["id"]
        detail = requests.get(
            f"https://api.themoviedb.org/3/movie/{tmdb_id}"
            f"?api_key={TMDB_API_KEY}&language=ja-JP&append_to_response=credits",
            timeout=10
        ).json()

        director = next(
            (c["name"] for c in detail.get("credits", {}).get("crew", []) if c.get("job") == "Director"),
            ""
        )
        country  = ", ".join(c.get("name", "") for c in detail.get("production_countries", []))
        runtime  = str(detail.get("runtime", ""))
        genre    = ", ".join(g.get("name", "") for g in detail.get("genres", []))
        poster   = detail.get("poster_path", "")

        return {
            "director": director, "country": country,
            "runtime": runtime, "genre": genre,
            "tmdb_id": str(tmdb_id), "poster_path": poster
        }
    except Exception as e:
        print(f"    TMDB取得失敗 ({title}): {e}")
        return {}

# ===== メイン =====
def main():
    print("=== Filmarks → Sheets 差分同期 ===\n")

    service  = get_sheets_service()
    existing = get_existing_titles(service)
    print(f"既存タイトル数: {len(existing)}\n")

    new_marks = []
    for page in range(1, MAX_PAGES + 1):
        print(f"Filmarks ページ {page} を確認中...")
        marks = scrape_filmarks_page(page)
        if not marks:
            break

        page_new = [m for m in marks if m["title"] not in existing]
        new_marks.extend(page_new)
        print(f"  → {len(page_new)} 件が新規")

        # 全件が既存 → それ以降もないので終了
        if len(page_new) == 0:
            print("  全件既存のため終了")
            break

        time.sleep(1)

    print(f"\n新規エントリー合計: {len(new_marks)} 件\n")
    if not new_marks:
        print("追加なし。終了します。")
        return

    rows = []
    for m in new_marks:
        print(f"  [{m['title']}] TMDB取得中...", end=" ", flush=True)
        tmdb = fetch_tmdb_metadata(m["title"], m["year"])
        print("OK" if tmdb else "データなし")
        rows.append([
            m["title"],
            m["year"],
            m["score"],
            m["comment"],
            m["url"],
            tmdb.get("director", ""),
            tmdb.get("country", ""),
            tmdb.get("runtime", ""),
            tmdb.get("genre", ""),
            tmdb.get("tmdb_id", ""),
            tmdb.get("poster_path", "")
        ])
        time.sleep(0.5)

    added = append_to_sheet(service, rows)
    print(f"\n✅ 完了: {added} 件をシートに追加しました")
    for r in rows:
        print(f"  - {r[0]} ({r[1]})")

if __name__ == "__main__":
    main()
