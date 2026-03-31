import time
import requests
from config import THREADS_USER_ID, THREADS_ACCESS_TOKEN, CATEGORY_TAGS

THREADS_API = "https://graph.threads.net/v1.0"


def create_container(text: str, reply_to_id: str = "") -> str | None:
    url = f"{THREADS_API}/{THREADS_USER_ID}/threads"
    params = {
        "media_type":   "TEXT",
        "text":         text,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    if reply_to_id:
        params["reply_to_id"] = reply_to_id

    for attempt in range(3):
        try:
            res = requests.post(url, params=params, timeout=30)
            data = res.json()
            if "id" in data:
                return data["id"]
            print(f"  [Poster] Container error: {data}")
            return None
        except requests.exceptions.ReadTimeout:
            print(f"  [Poster] Timeout on create_container attempt {attempt + 1}/3")
            if attempt < 2:
                time.sleep(5)

    print(f"  [Poster] create_container failed after 3 attempts")
    return None


def publish_container(container_id: str) -> str | None:
    url = f"{THREADS_API}/{THREADS_USER_ID}/threads_publish"
    params = {
        "creation_id":  container_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }

    for attempt in range(3):
        try:
            res = requests.post(url, params=params, timeout=30)
            data = res.json()
            if "id" in data:
                return data["id"]
            print(f"  [Poster] Publish error: {data}")
            return None
        except requests.exceptions.ReadTimeout:
            print(f"  [Poster] Timeout on publish_container attempt {attempt + 1}/3")
            if attempt < 2:
                time.sleep(5)

    print(f"  [Poster] publish_container failed after 3 attempts")
    return None


def refresh_token() -> bool:
    """アクセストークンを自動更新（60日有効→延長）"""
    url = "https://graph.threads.net/refresh_access_token"
    params = {
        "grant_type":   "th_refresh_token",
        "access_token": THREADS_ACCESS_TOKEN,
    }

    for attempt in range(3):
        try:
            res = requests.get(url, params=params, timeout=30)
            data = res.json()
            if "access_token" in data:
                print(f"  [Poster] Token refreshed successfully")
                return True
            print(f"  [Poster] Token refresh failed: {data}")
            return False
        except requests.exceptions.ReadTimeout:
            print(f"  [Poster] Timeout on refresh_token attempt {attempt + 1}/3")
            if attempt < 2:
                time.sleep(5)
        except Exception as e:
            print(f"  [Poster] Token refresh error: {e}")
            return False

    print(f"  [Poster] refresh_token failed after 3 attempts")
    return False


def post_tweet(tweet_text: str, original_url: str = "", category: str = "other") -> dict:
    """
    Threadsに投稿する
    - 本投稿: テキスト + トピックタグ
    - リプライ: 元記事フルURL
    """
    # URLが本文に含まれている場合は取り除く
    main_text = tweet_text.split("\nhttp")[0].split("\nhttps")[0].strip()

    # カテゴリに応じたトピックタグを付与
    tag = CATEGORY_TAGS.get(category, "")
    if tag:
        main_text = f"{main_text}\n{tag}"
        print(f"  [Poster] Topic tag: {tag}")

    # ① 本投稿コンテナ作成
    container_id = create_container(main_text)
    if not container_id:
        return {"success": False}
    time.sleep(2)

    # ② 本投稿を公開
    post_id = publish_container(container_id)
    if not post_id:
        return {"success": False}

    print(f"  [Poster] Posted: {post_id}")
    print(f"           Text: {main_text[:80]}...")

    # ③ フルURLをリプライに投稿（直後）
    if original_url:
        time.sleep(3)
        reply_container_id = create_container(
            f"🔗 Source: {original_url}",
            reply_to_id=post_id
        )
        if reply_container_id:
            time.sleep(2)
            reply_id = publish_container(reply_container_id)
            if reply_id:
                print(f"  [Poster] Reply with URL: {reply_id}")

    return {"post_id": post_id, "success": True}
