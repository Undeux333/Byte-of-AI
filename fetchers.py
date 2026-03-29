import time
import re
import html
import requests
import feedparser
from datetime import datetime, timedelta, timezone

import state_manager as sm
from config import RSS_SOURCES, REDDIT_SOURCES, HN_TOP_LIMIT, HN_MIN_SCORE

HEADERS = {"User-Agent": "Mozilla/5.0 (GlobalNewsBot/2.0)"}


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _story(title, url, source, category, summary="", weight=5) -> dict:
    return {
        "title":    _clean(title)[:240],
        "url":      url.strip(),
        "source":   source,
        "category": category,
        "summary":  _clean(summary)[:500],
        "weight":   weight,
    }


# ─────────────────────────────────────────────────────────────
# RSS
# ─────────────────────────────────────────────────────────────
def fetch_rss(state: dict) -> list[dict]:
    results = []
    cutoff  = datetime.now(timezone.utc) - timedelta(hours=30)

    for cfg in RSS_SOURCES:
        try:
            feed  = feedparser.parse(cfg["url"])
            count = 0
            for entry in feed.entries[:18]:
                url   = entry.get("link", "")
                title = _clean(entry.get("title", ""))
                if not url or not title or sm.is_seen(state, url):
                    continue
                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub:
                    pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        continue
                summary = _clean(entry.get("summary", entry.get("description", "")))
                results.append(_story(title, url, cfg["name"], cfg["category"], summary, cfg["weight"]))
                count += 1
            print(f"  [RSS] {cfg['name']:<20} → {count}")
        except Exception as e:
            print(f"  [RSS] {cfg['name']:<20} → ERROR: {e}")
        time.sleep(0.2)

    return results


# ─────────────────────────────────────────────────────────────
# Reddit
# ─────────────────────────────────────────────────────────────
def fetch_reddit(state: dict) -> list[dict]:
    results = []
    for sub in REDDIT_SOURCES:
        url = f"https://www.reddit.com/r/{sub['name']}/{sub['sort']}.json?limit={sub['limit']}"
        try:
            res   = requests.get(url, headers=HEADERS, timeout=10)
            posts = res.json().get("data", {}).get("children", [])
            count = 0
            for post in posts:
                p     = post.get("data", {})
                ups   = p.get("ups", 0)
                title = p.get("title", "")
                link  = p.get("url") or f"https://reddit.com{p.get('permalink','')}"
                if ups < sub["min_ups"] or not title or sm.is_seen(state, link):
                    continue
                if p.get("stickied"):
                    continue
                weight = min(9, 5 + int(ups / 5000))
                results.append(_story(title, link, f"r/{sub['name']}", sub["category"],
                                      p.get("selftext", "")[:400], weight))
                count += 1
            print(f"  [Reddit] r/{sub['name']:<16} → {count}")
        except Exception as e:
            print(f"  [Reddit] r/{sub['name']:<16} → ERROR: {e}")
        time.sleep(0.8)
    return results


# ─────────────────────────────────────────────────────────────
# Hacker News
# ─────────────────────────────────────────────────────────────
def fetch_hn(state: dict) -> list[dict]:
    results = []
    try:
        top_ids = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            headers=HEADERS, timeout=10
        ).json()[:HN_TOP_LIMIT]

        count = 0
        for sid in top_ids:
            item  = requests.get(
                f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                headers=HEADERS, timeout=8
            ).json()
            if not item or item.get("type") != "story":
                continue
            score = item.get("score", 0)
            title = item.get("title", "")
            url   = item.get("url") or f"https://news.ycombinator.com/item?id={sid}"
            if score < HN_MIN_SCORE or not title or sm.is_seen(state, url):
                continue
            weight = min(9, 5 + int(score / 200))
            results.append(_story(title, url, "HackerNews", "tech",
                                  f"HN Score: {score}", weight))
            count += 1
            time.sleep(0.1)
        print(f"  [HN]                      → {count}")
    except Exception as e:
        print(f"  [HN] ERROR: {e}")
    return results


# ─────────────────────────────────────────────────────────────
# 全ソース統合
# ─────────────────────────────────────────────────────────────
def collect_all(state: dict) -> list[dict]:
    print("\n[Fetcher] Collecting from all sources...\n")
    all_stories: list[dict] = []

    print("── RSS ──")
    all_stories.extend(fetch_rss(state))

    print("\n── Reddit ──")
    all_stories.extend(fetch_reddit(state))

    print("\n── HackerNews ──")
    all_stories.extend(fetch_hn(state))

    seen_in_run: set[str] = set()
    deduped = []
    for s in all_stories:
        if s["url"] not in seen_in_run:
            seen_in_run.add(s["url"])
            deduped.append(s)

    print(f"\n[Fetcher] {len(deduped)} unique new stories")
    return deduped
