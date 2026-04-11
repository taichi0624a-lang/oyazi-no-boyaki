import os
import re
import sys
import io
import json
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

app = Flask(__name__)
CORS(app)

FILMARKS_EMAIL = os.environ.get("FILMARKS_EMAIL", "taichi0624a@gmail.com")
FILMARKS_PASS  = os.environ.get("FILMARKS_PASS",  "sally0624")
PORT = int(os.environ.get("PORT", 5000))

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9",
})
logged_in = False
current_user_id = ""

def get_csrf_token(html=None):
    if html is None:
        r = session.get("https://filmarks.com/")
        html = r.text
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", {"name": "csrf-token"})
    if meta:
        return meta.get("content", "")
    inp = soup.find("input", {"name": "authenticity_token"})
    if inp:
        return inp.get("value", "")
    return ""

def login():
    global logged_in, current_user_id
    r = session.get("https://filmarks.com/login")
    csrf = get_csrf_token(r.text)

    resp = session.post("https://filmarks.com/login", data={
        "authenticity_token": csrf,
        "user[email]":        FILMARKS_EMAIL,
        "user[password]":     FILMARKS_PASS,
        "user[remember_me]":  "1",
        "button":             ""
    }, allow_redirects=True)

    if "filmarks.com" in resp.url and "login" not in resp.url:
        logged_in = True
        # ユーザーIDをページから取得
        current_user_id = extract_user_id(resp.text)
        print(f"ログイン成功: {resp.url} user_id={current_user_id}")
        return True
    print(f"ログイン失敗: {resp.url}")
    return False

def extract_user_id(html):
    """HTMLからログイン中ユーザーのIDを取得"""
    soup = BeautifulSoup(html, "html.parser")
    # meta タグ
    for meta in soup.find_all("meta"):
        content = meta.get("content", "")
        if "/users/" in content:
            m = re.search(r'/users/(\d+)', content)
            if m:
                return m.group(1)
    # data属性
    for tag in soup.find_all(attrs={"data-user-id": True}):
        return tag["data-user-id"]
    # scriptタグのJSON
    for script in soup.find_all("script"):
        txt = script.string or ""
        m = re.search(r'"currentUserId"\s*:\s*(\d+)', txt)
        if m:
            return m.group(1)
        m = re.search(r'"userId"\s*:\s*(\d+)', txt)
        if m:
            return m.group(1)
    return ""

def get_mark_data_from_movie_page(movie_id, mark_id):
    """映画ページからマークデータを取得"""
    session.headers.update({"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"})
    r = session.get(f"https://filmarks.com/movies/{movie_id}")
    csrf = get_csrf_token(r.text)

    if r.status_code != 200:
        return {}, csrf

    soup = BeautifulSoup(r.text, "html.parser")
    html_text = r.text

    result = {}

    # ① scriptタグからJSONデータを探す
    for script in soup.find_all("script"):
        txt = script.string or ""
        # mark_id が含まれるJSONオブジェクトを探す
        patterns = [
            r'\{[^{}]{0,500}"id"\s*:\s*' + str(mark_id) + r'[^{}]{0,500}\}',
        ]
        for pat in patterns:
            m = re.search(pat, txt)
            if m:
                try:
                    obj = json.loads(m.group(0))
                    if obj.get("id") == int(mark_id) or str(obj.get("id")) == str(mark_id):
                        result = obj
                        print(f"scriptタグからマークデータ取得: {obj}")
                        break
                except Exception:
                    pass
        if result:
            break

    # ② data-props属性を探す
    if not result:
        for tag in soup.find_all(attrs={"data-props": True}):
            try:
                props = json.loads(tag.get("data-props", "{}"))
                def find_mark(obj):
                    if isinstance(obj, dict):
                        if str(obj.get("id", "")) == str(mark_id):
                            return obj
                        for v in obj.values():
                            found = find_mark(v)
                            if found:
                                return found
                    elif isinstance(obj, list):
                        for item in obj:
                            found = find_mark(item)
                            if found:
                                return found
                    return None
                found = find_mark(props)
                if found:
                    result = found
                    print(f"data-propsからマークデータ取得: {found}")
                    break
            except Exception:
                pass

    # ③ スコアだけでもHTMLから取得
    if not result:
        score_tag = soup.find(class_="c-rating__score")
        if score_tag:
            result["score"] = score_tag.get_text(strip=True)
        print(f"HTMLからスコアのみ取得: score={result.get('score', 'なし')}")

    return result, csrf

def post_comment(movie_url: str, comment: str):
    global logged_in, current_user_id

    if not logged_in:
        if not login():
            return {"ok": False, "error": "ログインに失敗しました"}

    m_movie = re.search(r'/movies/(\d+)', movie_url)
    m_mark  = re.search(r'mark-(\d+)', movie_url)
    if not m_movie or not m_mark:
        return {"ok": False, "error": "URLからmovie_id/mark_idを取得できません"}

    movie_id = m_movie.group(1)
    mark_id  = m_mark.group(1)

    mark_data, csrf = get_mark_data_from_movie_page(movie_id, mark_id)

    score      = str(mark_data.get("score", "") or "")
    created_at = str(mark_data.get("created_at", "") or mark_data.get("createdAt", "") or "")
    count      = str(mark_data.get("count", "") or "")
    user_id    = str(mark_data.get("user_id", "") or mark_data.get("userId", "") or current_user_id or "")

    print(f"投稿データ: movie={movie_id} mark={mark_id} score={score} user_id={user_id}")

    session.headers.update({
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    })

    data = {
        "id":                mark_id,
        "movieId":           movie_id,
        "animeSeriesId":     "",
        "animeSeasonId":     "",
        "dramaSeriesId":     "",
        "dramaSeasonId":     "",
        "review":            comment,
        "score":             score,
        "isSpoiler":         "false",
        "createdAt":         created_at,
        "count":             count,
        "tags[]":            "",
        "userId":            user_id,
        "viewingRecords[]":  "",
        "isTwitterShare":    "0",
        "social[twitter]":   "false",
        "isActive":          "true",
        "show":              "true",
        "isApiProcessing":   "true"
    }

    resp = session.post(
        f"https://filmarks.com/movies/{movie_id}/marks",
        headers={
            "x-csrf-token":     csrf,
            "Content-Type":     "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer":          f"https://filmarks.com/movies/{movie_id}"
        },
        data=data
    )

    print(f"投稿結果: {resp.status_code} body={resp.text[:300]}")

    if resp.status_code in (200, 201):
        return {"ok": True}
    elif resp.status_code in (401, 403, 302):
        logged_in = False
        return post_comment(movie_url, comment)
    else:
        return {"ok": False, "error": f"HTTP {resp.status_code}", "detail": resp.text[:200]}

@app.route("/post-comment", methods=["POST"])
def api_post_comment():
    data     = request.get_json()
    mark_url = data.get("markUrl", "")
    comment  = data.get("comment", "")
    if not mark_url or not comment:
        return jsonify({"ok": False, "error": "markUrl と comment が必要です"})
    result = post_comment(mark_url, comment)
    return jsonify(result)

@app.route("/health")
def health():
    return jsonify({"ok": True, "logged_in": logged_in, "user_id": current_user_id})

if __name__ == "__main__":
    login()
    print(f"\n=== Filmarks連携サーバー起動 ===")
    print(f"URL: http://localhost:{PORT}\n")
    app.run(host="0.0.0.0", port=PORT)
