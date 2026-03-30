#!/usr/bin/env python3
# main.py — メインパイプライン（本投稿のみ・画像なし）

import sys
from datetime import datetime, timezone

import state_manager as sm
import fetchers
import scorer
import poster
from config import COLLECTION_INTERVAL_HOURS

DRY_RUN = "--dry-run" in sys.argv


def run():
    print(f"\n{'='*60}")
    print(f"  BOT PIPELINE  [{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}]")
    print(f"  DRY RUN: {DRY_RUN}")
    print(f"{'='*60}\n")

    state = sm.load()
    stats = sm.get_stats(state)
    print(f"[State] Queue={stats['queue_size']}  Posted={stats['total_posted']}  "
          f"SeenURLs={stats['seen_urls']}")

    # ── Step 1: 収集が必要かチェック ─────────────────────────────
    if sm.collection_needed(state, COLLECTION_INTERVAL_HOURS):
        print(f"\n[Pipeline] Collection needed. Running...\n")

        stories = fetchers.collect_all(state)
        for s in stories:
            sm.mark_seen(state, s["url"])

        if stories:
            # top_n=2：2時間ごとの収集で1時間おきに1件投稿するため2件生成
            candidates = scorer.score_all(stories, top_n=2)
            for c in candidates:
                sm.add_to_queue(state, {
                    "tweet":          c["tweet"],
                    "buzz_score":     c.get("buzz_score", 0),
                    "original_title": c.get("original_title", ""),
                    "url":            c.get("url", ""),
                    "source":         c.get("source", ""),
                    "category":       c.get("category", "other"),
                })
            state["stats"]["total_collected"] = \
                state["stats"].get("total_collected", 0) + len(candidates)
            print(f"\n[Pipeline] Added {len(candidates)} items to queue.")

        sm.mark_collected(state)
        sm.save(state)
        print("[Pipeline] State saved after collection.\n")
    else:
        print("[Pipeline] Collection not needed yet.\n")

    # ── Step 2: 投稿 ──────────────────────────────────────────────
    item = sm.pop_next(state)
    if not item:
        print("[Pipeline] Queue empty — nothing to post.")
        sm.save(state)
        return

    print(f"[Pipeline] Posting next item...")
    print(f"  Tweet: {item['tweet'][:100]}...")

    if DRY_RUN:
        print("\n[Pipeline] DRY RUN — skipping actual post.")
        print(f"\n--- TWEET PREVIEW ---\n{item['tweet']}\n---")
    else:
        result = poster.post_tweet(tweet_text=item["tweet"])
        if result.get("success"):
            sm.mark_posted(state)
            print(f"[Pipeline] Posted successfully!")
        else:
            state["queue"].insert(0, item)
            print("[Pipeline] Post failed — item returned to queue.")

    sm.save(state)
    stats = sm.get_stats(state)
    print(f"\n[Stats] Queue={stats['queue_size']}  TotalPosted={stats['total_posted']}")


if __name__ == "__main__":
    run()
