import json
import re
from datetime import datetime, timezone
from google import genai

from config import (
    GEMINI_API_KEY, GEMINI_MODEL,
    POSTS_PER_COLLECTION, CARRYOVER_MAX, CARRYOVER_TTL_HOURS
)

client = genai.Client(api_key=GEMINI_API_KEY)

# ── Rule-based pre-scoring ────────────────────────────────────────────────────
HIGH_VALUE_SOURCES = {
    "BBC World": 30, "Reuters": 30, "NPR News": 28, "NYT World": 28,
    "HackerNews": 25, "Al Jazeera": 22, "The Guardian": 22,
    "ESPN": 20, "BBC Sport": 20, "TechCrunch": 20, "The Ringer": 18,
    "Variety": 18, "Deadline": 18, "ScienceDaily": 18,
    "The Verge": 16, "Ars Technica": 16, "Wired": 16,
    "Billboard": 15, "WSJ": 20, "New Scientist": 15,
    "Psychology Today": 18, "PsyPost": 16,
    "Rolling Stone": 15, "IGN": 14, "Kotaku": 13,
    "Refinery29": 13, "Cosmopolitan": 12,
    "Lifehacker": 14, "Upworthy": 12, "Good News Network": 11,
}

CATEGORY_BONUS = {
    "world": 15, "sports": 12, "entertainment": 11,
    "tech": 11, "science": 10, "psychology": 12,
    "lifestyle": 10, "business": 8, "other": 5,
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
    for s in stories:
        s["rule_score"] = rule_score(s)
    stories_sorted = sorted(stories, key=lambda x: x["rule_score"], reverse=True)
    selected, source_count = [], {}
    for s in stories_sorted:
        src = s.get("source", "")
        if source_count.get(src, 0) < 2:
            selected.append(s)
            source_count[src] = source_count.get(src, 0) + 1
        if len(selected) >= n:
            break
    return selected

# ── Gemini prompt ─────────────────────────────────────────────────────────────
SCORING_PROMPT = """You are a witty American in your 30s running a viral Threads account.
You write like a real human — casual, sharp, and funny without trying too hard.

TARGET AUDIENCE: Americans aged 10-30, male and female equally.

CONTENT MIX — pick at most 2 stories from the same category:
- Comedy / memes / relatable moments (20%)
- Work-life balance / job culture (15%)
- World news / political irony (15%)
- Dating / psychology / mental health (15%)
- Nostalgia / pop culture (10%)
- AI / tech irony (10%)
- Sports moments (10%)
- Chaos / food / feel-good / science facts / TIPS (5%)

POST STRUCTURE — 3 parts, natural sentence flow:
1. The fact — state it bluntly (1-2 sentences)
2. The twist — sharp observation or unexpected reframe (1-2 sentences)
3. The landing — 5 words or fewer, cut off abruptly

STYLE RULES:
- Write like someone talking, not writing
- Casual American English: contractions, lowercase ok, imperfect punctuation fine
- Natural spoken phrases: "ok but", "wait", "honestly", "I mean", "at this point", "sure", "right?", "wild", "no but seriously"
- NEVER use: "lol", "ngl", "tbh" — those are typed, not spoken
- No hashtags. No emojis. No URLs in the post.
- Dark humor OK if it punches UP at power/institutions — never at victims
- Sensitive topics OK: sex (as humor/observation, not explicit), politics (irony not partisan), mental health (relatable not clinical)
- The landing should make people want to reply WITHOUT asking them to
- Target 150-200 characters total. Never exceed 300.

LANDING LINE RULES — vary the technique across the 4 posts:
For news / lifestyle / psychology / comedy posts, use ONE of:
- Pretend ignorance: "it has never met me." / "nobody told it." / "they don't know."
- Self-contradicting confession: "I've had four already." / "I do this too." / "asking for myself."
- Absurd defense of the wrong thing: "the ocean didn't do anything wrong." / "the dishes are innocent."
- Defeatist acceptance: "anyway." / "this is fine." / "sure." / "ok."
- Off-target conclusion: "that's a tomorrow problem." / "insurance doesn't cover it either." / "not my department."

For science / TIPS / tech facts posts, use ONE of:
- Humble comparison: "meanwhile my laptop." / "we have wifi and still."
- Dry admiration: "we built this." / "69KB. let that sink in."
- Absurd scale: "that's it. that's the post." / "just so we're clear."

The reader should finish the joke in their head — that moment is the laugh.
Do NOT repeat the same landing technique across the 4 posts.

BUZZ SCORE CRITERIA:
90-100: Will spark strong opinions, "same" replies, or debates
70-89: Funny and relatable, will get likes and reposts
50-69: Interesting but niche audience
below 50: Skip this story

Among the {top_n} posts, vary the tone:
- 1-2 posts: sharp irony or political observation
- 1 post: dry understatement or self-deprecating
- 1 post: absurd or surprising fact with unexpected landing

Here are {n} news stories. Do TWO things:
1. Pick the BEST {top_n} stories (max 2 from same category, prioritize buzz_score 70+)
2. Write ONE post per story following ALL rules above

Stories:
{stories}

Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "selections": [
    {{
      "index": <0-based story index>,
      "buzz_score": <0-100>,
      "post": "<150-300 chars, no URL, follow all style rules above>"
    }}
  ]
}}
"""

# ── Carryover logic ───────────────────────────────────────────────────────────

def load_carryover(state: dict) -> list[dict]:
    """有効期限内の持ち越し候補を取得"""
    now = datetime.now(timezone.utc)
    carryover = []
    for item in state.get("carryover_candidates", []):
        try:
            added_at = datetime.fromisoformat(item.get("added_at", ""))
            if added_at.tzinfo is None:
                added_at = added_at.replace(tzinfo=timezone.utc)
            hours_old = (now - added_at).total_seconds() / 3600
            if hours_old <= CARRYOVER_TTL_HOURS:
                carryover.append(item)
        except Exception:
            continue
    print(f"  [Scorer] Loaded {len(carryover)} carryover candidates (within {CARRYOVER_TTL_HOURS}h)")
    return carryover

def save_carryover(state: dict, rejected: list[dict]):
    """ふるい落とされた上位候補を持ち越し保存"""
    now = datetime.now(timezone.utc).isoformat()
    seen_urls = set(state.get("seen_urls", []))
    candidates = []
    for item in rejected[:CARRYOVER_MAX]:
        if item.get("url", "") not in seen_urls:
            item["added_at"] = now
            candidates.append(item)
    state["carryover_candidates"] = candidates
    print(f"  [Scorer] Saved {len(candidates)} carryover candidates")

# ── Main scoring ──────────────────────────────────────────────────────────────

def score_all(stories: list[dict], state: dict) -> list[dict]:
    """
    ① ルール予備選定（20件）
    ② 持ち越し候補と合算（最大28件）
    ③ Geminiでスコアリング＋投稿生成（1回）
    ④ 残り上位8件を持ち越し保存
    """
    print(f"\n[Scorer] Pre-selecting from {len(stories)} stories...")
    candidates = preselect(stories, n=20)

    # 持ち越し候補を追加
    carryover = load_carryover(state)
    seen_urls = set(state.get("seen_urls", []))
    for item in carryover:
        if item.get("url", "") not in seen_urls:
            candidates.append(item)

    # 重複除去
    seen = set()
    unique = []
    for c in candidates:
        url = c.get("url", "")
        if url not in seen:
            seen.add(url)
            unique.append(c)
    candidates = unique

    print(f"[Scorer] Sending {len(candidates)} stories to {GEMINI_MODEL}...\n")

    stories_text = "\n".join([
        f"[{i}] [{s.get('category','?').upper()}] {s['title']} (Source: {s['source']})"
        + (f"\n    Summary: {s['summary'][:150]}" if s.get('summary') else "")
        for i, s in enumerate(candidates)
    ])

    prompt = SCORING_PROMPT.format(
        n=len(candidates),
        top_n=POSTS_PER_COLLECTION,
        stories=stories_text,
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

    selected_indices = set()
    output = []

    for sel in result.get("selections", [])[:POSTS_PER_COLLECTION]:
        idx = sel.get("index", 0)
        if idx >= len(candidates):
            continue
        story    = candidates[idx]
        post_raw = sel.get("post", "").strip()
        if not post_raw:
            continue

        selected_indices.add(idx)
        output.append({
            "tweet":          post_raw,
            "short_url":      "",
            "original_url":   story.get("url", ""),
            "buzz_score":     sel.get("buzz_score", 0),
            "original_title": story["title"],
            "url":            story.get("url", ""),
            "source":         story.get("source", ""),
            "category":       story.get("category", "other"),
        })
        print(f"  [Scorer] Selected [{story['category']}] {story['title'][:60]}...")
        print(f"           Post: {post_raw[:80]}...")

    # 持ち越し候補保存（選ばれなかった上位8件）
    rejected = [c for i, c in enumerate(candidates) if i not in selected_indices]
    rejected_sorted = sorted(rejected, key=lambda x: x.get("rule_score", 0), reverse=True)
    save_carryover(state, rejected_sorted)

    print(f"\n[Scorer] Generated {len(output)}/{POSTS_PER_COLLECTION} posts")
    return output
