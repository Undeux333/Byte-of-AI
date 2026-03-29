#!/usr/bin/env python3
"""
main.py — GitHub Actions から呼ばれるメインパイプライン
・収集が必要なら → collect & score → キューに追加
・キューに記事があれば → 画像生成 → 本投稿 + 引用RT
"""
import sys
from datetime import datetime, timezone

import state_manager as sm
import fetchers
import scorer
import image_gen
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
            candidates = scorer.score_all(stories)
            for c in candidates:
                sm.add_to_queue(state, {
                    "main_tweet":        c["main_tweet"],
                    "sub_tweet":         c["sub_tweet"],
                    "headline":          c.get("headline", c["original_title"][:60]),
                    "simple_explanation":c.get("simple_explanation", ""),
                    "emoji":             c.get("emoji", "📰"),
                    "color_hex":         c.get("color_hex", "#2C3E50"),
                    "category":          c.get("category", "other"),
                    "source":            c.get("source", ""),
                    "url":               c.get("url", ""),
                    "buzz_score":        c.get("buzz_score", 0),
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

    print(f"[Pipeline] Posting next item (score={item['buzz_score']})...")
    print(f"  Main : {item['main_tweet']}")
    print(f"  Sub  : {item['sub_tweet']}")

    # 画像生成
    img_path = image_gen.create_card(
        headline           = item["headline"],
        simple_explanation = item["simple_explanation"],
        emoji              = item["emoji"],
        category           = item["category"],
        color_hex          = item["color_hex"],
        source             = item["source"],
    )
    print(f"  Image: {img_path}")

    if DRY_RUN:
        print("\n[Pipeline] DRY RUN — skipping actual post.")
    else:
        result = poster.post_tweet_set(
            main_text  = item["main_tweet"],
            sub_text   = item["sub_tweet"],
            image_path = img_path,
        )
        if result.get("success"):
            sm.mark_posted(state)
            print(f"[Pipeline] Posted successfully!")
        else:
            # 投稿失敗した場合はキューの先頭に戻す
            state["queue"].insert(0, item)
            print("[Pipeline] Post failed — item returned to queue.")

    sm.save(state)
    stats = sm.get_stats(state)
    print(f"\n[Stats] Queue={stats['queue_size']}  TotalPosted={stats['total_posted']}")


if __name__ == "__main__":
    run()
