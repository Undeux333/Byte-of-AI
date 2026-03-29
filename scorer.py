# scorer.py — Geminiスコアリング＋ツイート生成（例文ベース・サブ投稿なし・画像なし）

import json
import re
import time
import requests
from google import genai

from config import GEMINI_API_KEY, GEMINI_MODEL, CATEGORY_COLORS

client = genai.Client(api_key=GEMINI_API_KEY)


# ── URL短縮 ───────────────────────────────────────────────────────────────

def shorten_url(url: str) -> str:
    try:
        res = requests.get(
            f"https://tinyurl.com/api-create.php?url={url}",
            timeout=5
        )
        if res.status_code == 200 and res.text.startswith("http"):
            return res.text.strip()
    except Exception:
        pass
    return url


# ── 予備選定（Geminiに渡す前に上位20件に絞る） ──────────────────────────

HIGH_VALUE_SOURCES = {
    "BBC World": 30, "Reuters": 30, "AP News": 28,
    "HackerNews": 25, "Al Jazeera": 22, "The Guardian": 22,
    "ESPN": 20, "BBC Sport": 20, "TechCrunch": 20,
    "Variety": 18, "Deadline": 18, "ScienceDaily": 18,
    "The Verge": 16, "Ars Technica": 16, "Wired": 16,
    "Billboard": 15, "CNN Business": 15, "New Scientist": 15,
}

CATEGORY_BONUS = {
    "world": 15, "sports": 12, "entertainment": 10,
    "tech": 10, "science": 8, "business": 8, "other": 5,
}


def rule_score(story: dict) -> int:
    score  = HIGH_VALUE_SOURCES.get(story.get("source", ""), 10)
    score += CATEGORY_BONUS.get(story.get("category", "other"), 5)
    score += min(10, story.get("weight", 5))
    if "HN Score:" in story.get("summary", ""):
        try:
            hn = int(re.search(r"HN Score: (\d+)", story["summary"]).group(1))
            score += min(15, hn // 100)
        except Exception:
            pass
    return min(100, score)


def preselect(stories: list[dict], n: int = 20) -> list[dict]:
    """同ソース最大2件制限で上位n件を選ぶ"""
    for s in stories:
        s["rule_score"] = rule_score(s)
    stories_sorted = sorted(stories, key=lambda x: x["rule_score"], reverse=True)
    selected = []
    source_count: dict[str, int] = {}
    for s in stories_sorted:
        src = s.get("source", "")
        if source_count.get(src, 0) < 2:
            selected.append(s)
            source_count[src] = source_count.get(src, 0) + 1
        if len(selected) >= n:
            break
    return selected


# ── Geminiプロンプト ──────────────────────────────────────────────────────

SCORING_PROMPT = """You are a witty American in your 30s running a viral Twitter account.
You write like a real human — casual, sharp, and funny without trying too hard.

Your tweet style must match these EXACT examples:

[NEWS EXAMPLE]
Israel just took out 3 journalists in Lebanon. Not militants.
Journalists. At this point "press freedom" is just a phrase
we say at awards shows.

[TECH EXAMPLE]
OpenAI raised another $40B. That's enough money to solve
climate change but sure, let's make chatbots smarter first.
Priorities I guess.

[SPORTS EXAMPLE]
Sabalenka just won the Miami Open again. At this point just
hand her the trophy in January and save everyone the trip.
Absolute unit.

Notice the pattern:
- State the fact bluntly and simply
- Add ONE sharp, dry observation or contrast
- End with a short punchy line (2-6 words) that lands the joke
- Casual American English: contractions, "At this point", "sure", "I guess", "honestly"
- NO hashtags. NO emojis. NO formal language. NOT a journalist. NOT a press release.
- Dark humor OK if it punches UP at power/institutions — never at victims
- Max 200 characters (URL will be added separately after)

Here are {n} news stories. Do TWO things:
1. Pick the BEST {top_n} stories Americans on Twitter will care about right now
2. Write ONE tweet per story following the exact style above

Stories:
{stories}

Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "selections": [
    {{
      "index": <0-based story index>,
      "buzz_score": <0-100, how viral this will be on US Twitter>,
      "tweet": "<max 200 chars, exact style as examples above>"
    }}
  ]
}}
"""


# ── メイン処理 ────────────────────────────────────────────────────────────

def score_all(stories: list[dict], top_n: int = 2) -> list[dict]:
    """
    ① ルールで20件に予備選定（Gemini不使用）
    ② Geminiに20件を渡してスコアリング＋上位top_n件のツイート生成（1リクエスト）
    ③ 短縮URLを付与して返す
    """
    print(f"\n[Scorer] Pre-selecting from {len(stories)} stories...")
    candidates = preselect(stories, n=20)
    print(f"[Scorer] Sending {len(candidates)} stories to {GEMINI_MODEL}...\n")

    stories_text = "\n".join([
        f"[{i}] [{s.get('category','?').upper()}] {s['title']} (Source: {s['source']})"
        for i, s in enumerate(candidates)
    ])

    prompt = SCORING_PROMPT.format(
        n        = len(candidates),
        top_n    = top_n,
        stories  = stories_text,
    )

    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        raw   = response.text.strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found")
        result = json.loads(raw[start:end])
    except Exception as e:
        print(f"  [Scorer] Gemini error: {e}")
        return []

    output = []
    for sel in result.get("selections", [])[:top_n]:
        idx = sel.get("index", 0)
        if idx >= len(candidates):
            continue
        story     = candidates[idx]
        tweet_raw = sel.get("tweet", "").strip()
        if not tweet_raw:
            continue

        # 短縮URL生成して末尾に付与
        short_url  = shorten_url(story.get("url", ""))
        tweet_full = f"{tweet_raw}\n{short_url}"

        output.append({
            "tweet":          tweet_full,
            "buzz_score":     sel.get("buzz_score", 0),
            "original_title": story["title"],
            "url":            story.get("url", ""),
            "source":         story.get("source", ""),
            "category":       story.get("category", "other"),
            "color_hex":      CATEGORY_COLORS.get(story.get("category", "other"), "#2C3E50"),
        })
        print(f"  [Scorer] Selected [{story['category']}] {story['title'][:55]}...")
        print(f"           Tweet: {tweet_raw[:80]}...")

    print(f"\n[Scorer] Generated {len(output)}/{top_n} tweets")
    return output
