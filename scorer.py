# scorer.py — ルールベーススコアリング + Geminiでツイート生成のみ

import json
import re
import time
from google import genai

from config import GEMINI_API_KEY, GEMINI_MODEL, CATEGORY_COLORS

client = genai.Client(api_key=GEMINI_API_KEY)

# ── ルールベーススコアリング ──────────────────────────────────────────────
# Geminiを使わず機械的にスコアを計算する

HIGH_VALUE_SOURCES = {
    "BBC World": 30, "Reuters": 30, "AP News": 28,
    "HackerNews": 25, "Al Jazeera": 22, "The Guardian": 22,
    "ESPN": 20, "BBC Sport": 20, "TechCrunch": 20,
    "Variety": 18, "Deadline": 18, "ScienceDaily": 18,
    "The Verge": 16, "Ars Technica": 16, "Wired": 16,
    "Billboard": 15, "CNN Business": 15, "New Scientist": 15,
}

BUZZ_KEYWORDS = [
    "breaking", "first", "record", "historic", "shock", "surprise",
    "just", "urgent", "alert", "major", "massive", "huge",
    "dies", "dead", "killed", "crash", "explosion", "war",
    "win", "wins", "champion", "victory", "beat", "defeat",
    "ban", "arrest", "arrested", "guilty", "verdict",
    "launch", "release", "reveal", "announce", "new",
    "biggest", "largest", "worst", "best", "only",
]

CATEGORY_BONUS = {
    "world":         15,
    "sports":        12,
    "entertainment": 10,
    "tech":          10,
    "science":       8,
    "business":      8,
    "other":         5,
}


def rule_score(story: dict) -> int:
    """Geminiを使わずにルールでスコアを計算（0〜100）"""
    score = 0

    # ソースボーナス
    score += HIGH_VALUE_SOURCES.get(story.get("source", ""), 10)

    # カテゴリボーナス
    score += CATEGORY_BONUS.get(story.get("category", "other"), 5)

    # キーワードボーナス（タイトルに含まれるバズワード）
    title_lower = story.get("title", "").lower()
    keyword_hits = sum(1 for kw in BUZZ_KEYWORDS if kw in title_lower)
    score += min(20, keyword_hits * 7)

    # ソース重みボーナス（fetchers.pyで設定した重み）
    score += min(10, story.get("weight", 5))

    # HackerNewsはsummaryにスコアが入っている
    summary = story.get("summary", "")
    if "HN Score:" in summary:
        try:
            hn_score = int(re.search(r"HN Score: (\d+)", summary).group(1))
            score += min(15, hn_score // 100)
        except Exception:
            pass

    return min(100, score)


def select_top(stories: list[dict], n: int) -> list[dict]:
    """ルールスコアで上位n件を選ぶ"""
    scored = []
    for s in stories:
        s["rule_score"] = rule_score(s)
        scored.append(s)
    scored.sort(key=lambda x: x["rule_score"], reverse=True)
    return scored[:n]


# ── Geminiによるツイート生成 ──────────────────────────────────────────────

PROMPT = """You are a globally viral American Twitter account. Analyze this story and respond ONLY with valid JSON.

Story:
  Title:    {title}
  Summary:  {summary}
  Source:   {source}
  Category: {category}

Respond ONLY with this exact JSON (no markdown, no explanation):
{{
  "main_tweet": "<EXACTLY under 100 chars. Written like a sharp American tweeter. No hashtags. Hook first.>",
  "sub_tweet": "<EXACTLY under 100 chars. Witty/dark-humorous American take, hot opinion, or smart advice. Must feel like a real American person — not a press release. No hashtags.>",
  "headline": "<8 words max. Punchy American headline.>",
  "simple_explanation": "<Explain to a curious American 10-year-old in 2-3 sentences. Simple words. Exciting.>",
  "emoji": "<single most fitting emoji>",
  "color_hex": "<hex color matching the mood>"
}}

Rules:
- main_tweet: strictly under 100 characters. Count every character.
- sub_tweet: strictly under 100 characters. Must add a NEW angle — humor, hot take, or advice. NOT a repeat.
- American English only: contractions, casual phrasing, American cultural references.
- Dark humor OK if non-discriminatory. No slurs, no hate speech.
"""


def generate_tweet(story: dict) -> dict | None:
    """選ばれた記事に対してGeminiでツイートを生成"""
    prompt = PROMPT.format(
        title    = story["title"][:200],
        summary  = story.get("summary", "")[:400],
        source   = story["source"],
        category = story.get("category", "other"),
    )
    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        raw   = response.text.strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON")
        result = json.loads(raw[start:end])

        result["main_tweet"] = result.get("main_tweet", "")[:100].strip()
        result["sub_tweet"]  = result.get("sub_tweet",  "")[:100].strip()

        result["original_title"] = story["title"]
        result["url"]            = story["url"]
        result["source"]         = story["source"]
        result["category"]       = story.get("category", "other")
        result["rule_score"]     = story.get("rule_score", 0)

        if not result.get("color_hex"):
            result["color_hex"] = CATEGORY_COLORS.get(story.get("category", "other"), "#2C3E50")

        return result

    except json.JSONDecodeError as e:
        print(f"    [Scorer] JSON error: {e}")
        return None
    except Exception as e:
        print(f"    [Scorer] API error: {e}")
        return None


def score_all(stories: list[dict], top_n: int = 4) -> list[dict]:
    """
    ① ルールベースで上位top_n件を選出（Geminiなし）
    ② 選ばれた件数分だけGeminiでツイート生成
    """
    print(f"\n[Scorer] Rule-based selection: {len(stories)} → top {top_n}\n")

    top_stories = select_top(stories, top_n)

    for s in top_stories:
        print(f"  Rule score {s['rule_score']:>3}/100  [{s['category']:<14}]  {s['title'][:55]}...")

    print(f"\n[Scorer] Generating tweets with Gemini ({len(top_stories)} requests)...\n")

    candidates = []
    for i, story in enumerate(top_stories, 1):
        print(f"  [{i}/{len(top_stories)}] {story['title'][:60]}...")
        result = generate_tweet(story)

        if result and result.get("main_tweet") and result.get("sub_tweet"):
            candidates.append(result)
            print(f"           → OK  main: {result['main_tweet'][:50]}...")
        else:
            print(f"           → ERROR (skipped)")

        if i < len(top_stories):
            time.sleep(4.0)   # Gemini rate limit

    print(f"\n[Scorer] Generated: {len(candidates)}/{len(top_stories)}")
    return candidates
