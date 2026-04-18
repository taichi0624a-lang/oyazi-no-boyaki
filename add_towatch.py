"""
TOWATCHシートに必見映画を追加 + TMDBでメタデータ補完
"""
import requests
import pickle
import time
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from googleapiclient.discovery import build

TMDB_API_KEY   = 'c6dc0382ae920c2cb5143ff6a7ce97e6'
SPREADSHEET_ID = '1Kqff4ogYLk6L5W-vIby1CijrOmCxLF1_axpZaWZNr80'
SHEET_NAME     = 'TOWATCH'

# ===== ここ数年の必見作 =====
TOWATCH_MOVIES = [
    # 2020-2025 国際映画 必見
    "TAR／ター",
    "アフターサン",
    "哀れなるものたち",
    "落下の解剖学",
    "関心領域",
    "オッペンハイマー",
    "キラーズ・オブ・ザ・フラワームーン",
    "パスト ライブス/過去の人生",
    "ホールドオーバーズ 置いてけぼりのホリディ",
    "アメリカン・フィクション",
    "コット、はじまりの夏",
    "ナイブズ・アウト グラス・オニオン",
    "ロボット・ドリームズ",
    "瞳をとじて",
    "シビル・ウォー アメリカ最後の日",
    "ザ・サブスタンス",
    "コンクラーベ",
    "憐れみの3章",
    "アノラ",
    "ブルタリスト",
    "デューン 砂の惑星",
    "デューン 砂の惑星PART2",
    "スパイダーマン アクロス・ザ・スパイダーバース",
    "マッドマックス フュリオサ",
    "エイリアン ロムルス",
    "ロングレッグス",
    "ヒット・マン",
    "ドッグマン",
    "MONOS モノス",
    "ヴェノム ザ・ラストダンス",
    # 2020-2025 日本映画 必見
    "青春18×2 君へと続く道",
    "湖の女たち",
    "違国日記",
    "八犬伝",
    "侍タイムスリッパー",
    "アイミタガイ",
    "若き見知らぬ者たち",
    # クラシック・名作 見逃し厳禁
    "ジョン・ウィック",
    "マトリックス",
    "ダークナイト ライジング",
    "インターステラー",
    "ラ・ラ・ランド",
]

def tmdb_search(title):
    r = requests.get('https://api.themoviedb.org/3/search/movie',
        params={'api_key': TMDB_API_KEY, 'query': title, 'language': 'ja-JP'})
    results = r.json().get('results', [])
    return results[0] if results else None

def tmdb_details(movie_id):
    r = requests.get(f'https://api.themoviedb.org/3/movie/{movie_id}',
        params={'api_key': TMDB_API_KEY, 'language': 'ja-JP', 'append_to_response': 'credits'})
    return r.json()

def get_director(credits):
    for c in credits.get('crew', []):
        if c.get('job') == 'Director':
            return c.get('name', '')
    return ''

def get_countries(details):
    return ', '.join(c.get('name','') for c in details.get('production_countries', []))

def main():
    with open('token.pickle', 'rb') as f:
        creds = pickle.load(f)
    service = build('sheets', 'v4', credentials=creds)

    # 既存タイトル取得（重複スキップ）
    res = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=f'{SHEET_NAME}!A2:A').execute()
    existing = set(r[0].strip() for r in res.get('values', []) if r)
    print(f'既存: {len(existing)}件\n')

    rows_to_add = []
    for title in TOWATCH_MOVIES:
        if title in existing:
            print(f'スキップ(既存): {title}')
            continue

        print(f'{title} ... ', end='', flush=True)
        movie = tmdb_search(title)
        if not movie:
            print('TMDBで見つからず → タイトルのみ追加')
            rows_to_add.append([title, '', '', '', '', '', '', ''])
            continue

        details = tmdb_details(movie['id'])
        year = (details.get('release_date') or '')[:4]
        runtime = details.get('runtime') or ''
        runtime_str = f'{runtime}分' if runtime else ''
        director = get_director(details.get('credits', {}))
        countries = get_countries(details)

        print(f'{year} / {director} / {countries}')
        rows_to_add.append([title, year, '', '', '', director, countries, runtime_str])
        time.sleep(0.3)

    if rows_to_add:
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{SHEET_NAME}!A1',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body={'values': rows_to_add}
        ).execute()
        print(f'\n{len(rows_to_add)}件追加完了')
    else:
        print('追加なし')

if __name__ == '__main__':
    main()
