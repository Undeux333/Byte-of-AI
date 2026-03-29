import tweepy
from config import (
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET,
)


def _clients():
    auth = tweepy.OAuth1UserHandler(
        TWITTER_API_KEY, TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET,
    )
    v1 = tweepy.API(auth)
    v2 = tweepy.Client(
        consumer_key        = TWITTER_API_KEY,
        consumer_secret     = TWITTER_API_SECRET,
        access_token        = TWITTER_ACCESS_TOKEN,
        access_token_secret = TWITTER_ACCESS_TOKEN_SECRET,
    )
    return v1, v2


def post_tweet_set(main_text: str, sub_text: str, image_path: str) -> dict:
    """
    ① 画像付きで本投稿
    ② 本投稿を引用リツイートしてサブ投稿
    Returns: {"main_id": ..., "sub_id": ..., "success": bool}
    """
    v1, v2 = _clients()

    # ── 画像アップロード ─────────────────────────────────────────
    media_id = None
    try:
        media    = v1.media_upload(filename=image_path)
        media_id = media.media_id
    except Exception as e:
        print(f"  [Poster] Image upload failed: {e} — posting without image")

    # ── 本投稿 ───────────────────────────────────────────────────
    try:
        kwargs = {"text": main_text}
        if media_id:
            kwargs["media_ids"] = [media_id]
        main_resp = v2.create_tweet(**kwargs)
        main_id   = str(main_resp.data["id"])
        print(f"  [Poster] Main tweet posted: {main_id}")
    except tweepy.TweepyException as e:
        print(f"  [Poster] Main tweet failed: {e}")
        return {"success": False}

    # ── サブ投稿（引用リツイート）────────────────────────────────
    quote_url = f"https://twitter.com/i/web/status/{main_id}"
    sub_full  = f"{sub_text}\n{quote_url}"
    try:
        sub_resp = v2.create_tweet(text=sub_full, quote_tweet_id=main_id)
        sub_id   = str(sub_resp.data["id"])
        print(f"  [Poster] Sub tweet  posted: {sub_id}")
    except tweepy.TweepyException as e:
        print(f"  [Poster] Sub tweet failed: {e}")
        sub_id = None

    return {"main_id": main_id, "sub_id": sub_id, "success": True}
