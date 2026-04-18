"""
スプレッドシートの空メタデータをTMDB APIで補完するスクリプト
- 製作年 (B列), 監督 (F列), 製作国 (G列), 上映時間 (H列) が空の行を対象
"""
import requests
import pickle
import time
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from googleapiclient.discovery import build

TMDB_API_KEY     = 'c6dc0382ae920c2cb5143ff6a7ce97e6'
SPREADSHEET_ID   = '1Kqff4ogYLk6L5W-vIby1CijrOmCxLF1_axpZaWZNr80'
SHEET_NAME       = 'シート1'

def tmdb_search(title):
    url = f'https://api.themoviedb.org/3/search/movie'
    r = requests.get(url, params={'api_key': TMDB_API_KEY, 'query': title, 'language': 'ja-JP'})
    data = r.json()
    results = data.get('results', [])
    return results[0] if results else None

def tmdb_details(movie_id):
    r = requests.get(
        f'https://api.themoviedb.org/3/movie/{movie_id}',
        params={'api_key': TMDB_API_KEY, 'language': 'ja-JP', 'append_to_response': 'credits'}
    )
    return r.json()

def get_director(credits):
    for c in credits.get('crew', []):
        if c.get('job') == 'Director':
            return c.get('name', '')
    return ''

def get_countries(details):
    countries = details.get('production_countries', [])
    return ', '.join(c.get('name', '') for c in countries)

def main():
    with open('token.pickle', 'rb') as f:
        creds = pickle.load(f)
    service = build('sheets', 'v4', credentials=creds)

    # シート全データ取得
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f'{SHEET_NAME}!A2:H'
    ).execute()
    rows = result.get('values', [])
    print(f'総行数: {len(rows)}')

    updates = []

    for i, row in enumerate(rows):
        row_num = i + 2  # ヘッダー行があるので+2

        title = row[0].strip() if len(row) > 0 else ''
        year  = row[1].strip() if len(row) > 1 else ''
        # 製作年(B)が既に入っていればスキップ
        if not title or year:
            continue

        print(f'[{row_num}] {title} ... ', end='', flush=True)

        movie = tmdb_search(title)
        if not movie:
            print('TMDBで見つからず')
            continue

        details = tmdb_details(movie['id'])
        release_year = (details.get('release_date') or '')[:4]
        runtime = details.get('runtime') or ''
        runtime_str = f'{runtime}分' if runtime else ''
        director = get_director(details.get('credits', {}))
        countries = get_countries(details)

        print(f'{release_year} / {director} / {countries} / {runtime_str}')

        # B列(製作年), F列(監督), G列(製作国), H列(上映時間) を更新
        updates.append({
            'range': f'{SHEET_NAME}!B{row_num}:B{row_num}',
            'values': [[release_year]]
        })
        updates.append({
            'range': f'{SHEET_NAME}!F{row_num}:H{row_num}',
            'values': [[director, countries, runtime_str]]
        })

        time.sleep(0.3)

    if updates:
        print(f'\n{len(updates)//2} 件を更新中...')
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={'valueInputOption': 'RAW', 'data': updates}
        ).execute()
        print('完了')
    else:
        print('更新対象なし')

if __name__ == '__main__':
    main()
