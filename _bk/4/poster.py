# poster.py — 本投稿のみ（サブ投稿なし・画像なし）

import tweepy
from config import (
    TWITTER_API_KEY, TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET,
)


def post_tweet(tweet_text: str) -> dict:
    """
    本投稿のみ実行（引用リツイートなし・画像なし）
    Returns: {"tweet_id": ..., "success": bool}
    """
    v2 = tweepy.Client(
        consumer_key        = TWITTER_API_KEY,
        consumer_secret     = TWITTER_API_SECRET,
        access_token        = TWITTER_ACCESS_TOKEN,
        access_token_secret = TWITTER_ACCESS_TOKEN_SECRET,
    )

    try:
        resp     = v2.create_tweet(text=tweet_text)
        tweet_id = str(resp.data["id"])
        print(f"  [Poster] Posted: {tweet_id}")
        print(f"           Text: {tweet_text[:80]}...")
        return {"tweet_id": tweet_id, "success": True}
    except tweepy.TweepyException as e:
        print(f"  [Poster] Error: {e}")
        return {"success": False}
