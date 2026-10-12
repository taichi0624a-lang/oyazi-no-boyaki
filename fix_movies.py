"""
movies_watched.json の中身を補完・整形する一回限りの修正スクリプト。
- id=0（TMDB未紐付け）作品を再照合して poster/監督/国/上映時間/ジャンル/あらすじ を補完
- 国名の英語→日本語 正規化（全件）
※ TMDB の実データのみ使用。確度の低いマッチは採用しない（レポート出力）。
"""
import json, io, sys, re, time, urllib.parse, urllib.request, difflib

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
KEY = 'c6dc0382ae920c2cb5143ff6a7ce97e6'
FILE = 'movies_watched.json'

# 版・媒体の表記ゆれ（検索時に剥がす）
SUF = [r'4Kデジタルリマスター', r'4Kレストア版?', r'4K ?デジタル・?リマスター版?', r'デジタル・?リマスター版?',
       r'リマスター版?', r'レストア版?', r'修復版', r'無修正完全版', r'完全無修正完全版', r'ノーカット ?完全版',
       r'完全版', r'特別篇', r'特別版', r'ディレクターズ・?カット版?', r'ディレクター?ズカット版?',
       r'ノーカット', r'無修正', r'公開\d+周年記念版', r'\d+周年記念版', r'記念版', r'final cut',
       r'【[^】]*】', r'（原題）', r'\(原題\)', r'／REVENGE', r'4K ?']

# 邦題で引けない有名作は英題/原題ヒントで再検索
ENG = {
  'コンクラーベ':'Conclave', 'アノラ':'Anora', 'ブルタリスト':'The Brutalist', 'ヒット・マン':'Hit Man',
  'MONOS モノス':'Monos', '恋の罪':'Guilty of Romance', 'ジョーズ　MEGAモンスターズ':'',
  'ウィッシュ・ミー・アウェイ（原題）':'Wish Me Away', '101匹わんちゃん Go Go！ ダルメシアン！！':'101 Dalmatians II Patchs London Adventure',
  'べイビーわるきゅーれ':'Baby Assassins', '食人族4Kリマスター無修正完全版':'Cannibal Holocaust',
  'ビデオドローム 4K ディレクターズカット版':'Videodrome', '悪い子バビー／アブノーマル':'Bad Boy Bubby',
  'ルチオ・フルチのザ・サイキック':'The Psychic Fulci', 'バスケット・ケース':'Basket Case',
  'GUNDA／グンダ':'Gunda', '戦場のメリークリスマス 4K 修復版':'Merry Christmas Mr. Lawrence',
  '旅立つ息子へ':'Here We Are', 'ウィッカーマン final cut':'The Wicker Man 1973',
  '⻤太郎誕生 ゲゲゲの謎':'鬼太郎誕生 ゲゲゲの謎', 'ロシナンテ':'Rocinante',
}
# 明確な誤マッチを避ける除外（タイトル→拾ってはいけないTMDB id）
BLOCK = {995926}  # 凶悪犯→「ベテラン 凶悪犯罪捜査班」は別物

COUNTRY = {
  'United States of America':'アメリカ','United States':'アメリカ','USA':'アメリカ','US':'アメリカ',
  'Japan':'日本','United Kingdom':'イギリス','UK':'イギリス','South Korea':'韓国','Korea':'韓国',
  'France':'フランス','Germany':'ドイツ','Italy':'イタリア','Spain':'スペイン','Hong Kong':'香港',
  'China':'中国','Taiwan':'台湾','Canada':'カナダ','Australia':'オーストラリア','Austria':'オーストリア',
  'Denmark':'デンマーク','Sweden':'スウェーデン','Norway':'ノルウェー','Finland':'フィンランド',
  'Ireland':'アイルランド','Netherlands':'オランダ','Belgium':'ベルギー','Switzerland':'スイス',
  'Russia':'ロシア','India':'インド','Mexico':'メキシコ','Brazil':'ブラジル','Argentina':'アルゼンチン',
  'Thailand':'タイ','New Zealand':'ニュージーランド','Poland':'ポーランド','Czech Republic':'チェコ',
  'Iran':'イラン','Israel':'イスラエル','Turkey':'トルコ','Greece':'ギリシャ','Portugal':'ポルトガル',
  'Hungary':'ハンガリー','Romania':'ルーマニア','Indonesia':'インドネシア','Philippines':'フィリピン',
  'Vietnam':'ベトナム','Chile':'チリ','Colombia':'コロンビア','Iceland':'アイスランド',
}
def norm_country(c):
    if not c: return c
    parts = re.split(r'[,/、]', c)
    out = []
    for p in parts:
        p = p.strip()
        out.append(COUNTRY.get(p, p))
    # ユニーク保持
    seen=[]; [seen.append(x) for x in out if x and x not in seen]
    return ', '.join(seen)

def clean(t):
    s = t
    for p in SUF: s = re.sub(p, '', s)
    s = s.replace('　', ' ').strip(' 　・-−ー！!')
    return re.sub(r'\s+', ' ', s).strip()

def get(url):
    try: return json.load(urllib.request.urlopen(url, timeout=15))
    except Exception: return None

def search(q, year=''):
    if not q: return []
    u = 'https://api.themoviedb.org/3/search/movie?api_key=%s&language=ja-JP&query=%s' % (KEY, urllib.parse.quote(q))
    if year: u += '&year=%s' % year
    r = get(u); return r.get('results', []) if r else []

def norm(s): return re.sub(r'[\s　・:：!！?？\.，,\-–—]', '', (s or '')).lower()

def choose(title, year):
    cq = clean(title)
    cands = search(cq, year) + (search(cq) if year else [])
    eng = ENG.get(title)
    if eng is not None:
        cands = search(eng, year) + search(eng) + cands
    # スコアリング: タイトル類似 + 年一致
    best=None; bs=-1
    nq = norm(cq); neng = norm(ENG.get(title,''))
    for r in cands:
        if r['id'] in BLOCK: continue
        rt = r.get('title') or ''; ro = r.get('original_title') or ''
        sim = max(difflib.SequenceMatcher(None, nq, norm(rt)).ratio(),
                  difflib.SequenceMatcher(None, nq, norm(ro)).ratio())
        if neng:
            sim = max(sim, difflib.SequenceMatcher(None, neng, norm(ro)).ratio())
        by = (r.get('release_date') or '')[:4]
        ym = 0
        if year and by:
            dy = abs(int(by)-int(year)); ym = 1.0 if dy==0 else (0.6 if dy==1 else (0.3 if dy<=2 else -0.3))
        score = sim + ym*0.5 + (0.15 if (norm(rt)==nq or norm(ro)==nq or (neng and norm(ro)==neng)) else 0)
        if score > bs: bs=score; best=r
    # 採用基準: 類似>=0.5 もしくは 完全一致 もしくは 英題ヒントあり
    if best and bs >= 0.5:
        return best, round(bs,2)
    return None, round(bs,2)

def details(mid):
    d = get('https://api.themoviedb.org/3/movie/%s?api_key=%s&language=ja-JP&append_to_response=credits' % (mid, KEY))
    if not d: return None
    director = ''
    for c in (d.get('credits',{}) or {}).get('crew',[]):
        if c.get('job')=='Director': director = c.get('name',''); break
    countries = [norm_country(c.get('name','')) for c in d.get('production_countries',[])]
    genres = [g.get('name','') for g in d.get('genres',[])]
    return {
        'id': d['id'],
        'poster_path': d.get('poster_path') or '',
        'backdrop_path': d.get('backdrop_path') or '',
        'overview': d.get('overview') or '',
        'release_date': d.get('release_date') or '',
        'year': (d.get('release_date') or '')[:4],
        'appDirector': director,
        'appCountry': ', '.join([c for c in countries if c]),
        'appRuntime': (str(d.get('runtime'))+'分') if d.get('runtime') else '',
        'appGenre': ', '.join(genres),
        'genre_ids': [g['id'] for g in d.get('genres',[])],
    }

def main():
    data = json.load(open(FILE, encoding='utf-8'))
    filled=0; unmatched=[]; report=[]
    for m in data:
        # 国名正規化（全件）
        if m.get('appCountry'):
            m['appCountry'] = norm_country(m['appCountry'])
        # id=0 の補完
        if not m.get('id'):
            best, sc = choose(m['title'], str(m.get('year','') or ''))
            if best:
                det = details(best['id'])
                time.sleep(0.12)
                if det and det['poster_path']:
                    # filmarksScore/Comment/Url/appStatus は保持
                    for k,v in det.items():
                        if k=='year':
                            m['year']=v or m.get('year',''); m['filmarksYear']=m['year']
                        else:
                            m[k]=v
                    filled+=1
                    report.append(('OK  ', m['title'], best.get('title',''), det['year'], sc))
                    time.sleep(0.12); continue
            unmatched.append(m['title'])
            report.append(('--  ', m['title'], best.get('title','') if best else '（なし）', '', sc))
            time.sleep(0.1)
    json.dump(data, open(FILE,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print('=== 補完レポート ===')
    for st,t,mt,y,sc in report:
        print('%s %-30s → %-26s %5s  score=%s' % (st, t[:30], mt[:26], y, sc))
    print('----')
    print('補完成功:', filled, '／ 未解決:', len(unmatched))
    print('未解決:', '、'.join(unmatched))
    # 全体の欠損再チェック
    nop=[x for x in data if not x.get('poster_path')]
    eng=[x for x in data if re.search(r'[A-Za-z]', (x.get('appCountry') or ''))]
    print('残ポスター無し:', len(nop), ' 国名に英字残り:', len(eng))

if __name__=='__main__':
    main()
