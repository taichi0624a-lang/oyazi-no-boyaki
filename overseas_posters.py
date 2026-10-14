"""
movies_watched.json のポスターを「海外版」優先に差し替える一回限りスクリプト。
TMDB /movie/{id}/images から、日本版(ja)を避けて
  オリジナル言語 → 英語(en) → テキストレス(国際版) の順で最良を選ぶ。
海外版が無ければ現状維持。
"""
import json, io, sys, time, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
KEY = 'c6dc0382ae920c2cb5143ff6a7ce97e6'
FILE = 'movies_watched.json'


def get(url):
    try:
        return json.load(urllib.request.urlopen(url, timeout=15))
    except Exception:
        return None


def orig_lang(mid):
    d = get(f'https://api.themoviedb.org/3/movie/{mid}?api_key={KEY}')
    return (d or {}).get('original_language', '') or ''


def overseas_poster(mid, orig):
    d = get(f'https://api.themoviedb.org/3/movie/{mid}/images?api_key={KEY}')
    if not d:
        return ''
    posters = d.get('posters', [])
    cands = [p for p in posters if (p.get('iso_639_1') or '') != 'ja']
    if not cands:
        return ''
    def rank(p):
        lang = p.get('iso_639_1') or ''
        if lang == orig and orig and orig != 'ja':
            pref = 4            # オリジナル言語のポスター＝本来の海外版
        elif lang == 'en':
            pref = 3            # 英語版
        elif lang == '':
            pref = 2            # テキストレス（国際版）
        else:
            pref = 1
        return (pref, p.get('vote_average', 0), p.get('vote_count', 0))
    cands.sort(key=rank, reverse=True)
    return cands[0].get('file_path', '') or ''


def main():
    data = json.load(open(FILE, encoding='utf-8'))
    targets = [m for m in data if m.get('id')]
    print(f'対象 {len(targets)} 本（id付き）')
    changed = 0
    for i, m in enumerate(targets):
        orig = orig_lang(m['id'])
        time.sleep(0.08)
        p = overseas_poster(m['id'], orig)
        time.sleep(0.08)
        if p and p != m.get('poster_path'):
            m['poster_path'] = p
            changed += 1
        if (i + 1) % 100 == 0:
            print(f'  {i+1}/{len(targets)} ... 差替 {changed}', flush=True)
    json.dump(data, open(FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'✅ 完了: {changed} 本を海外版ポスターに差替 → {FILE}')


if __name__ == '__main__':
    main()
