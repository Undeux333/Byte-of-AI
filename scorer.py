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
    # World News
    "BBC World": 28, "Reuters": 28, "NYT World": 26, "NPR News": 26,
    "The Guardian": 22, "Al Jazeera": 22,
    # Tech
    "HackerNews": 24, "TechCrunch": 20, "The Verge": 18,
    "Ars Technica": 18, "Wired": 18,
    # Sports
    "ESPN": 20, "BBC Sport": 20, "The Ringer": 18,
    # Psychology
    "Psychology Today": 18, "PsyPost": 17,
    # Entertainment（若者向け強化）
    "Billboard": 21, "IGN": 21, "Vulture": 21, "Complex": 21,
    "Polygon": 20, "Kotaku": 20,
    "Rolling Stone": 17, "Entertainment Weekly": 17, "IndieWire": 15,
    "Variety": 14, "Deadline": 14,
    # Lifestyle（若者向け強化）
    "The Cut": 20, "Cosmopolitan": 20, "Refinery29": 20,
    "Hypebeast": 18, "Lifehacker": 16,
    "Upworthy": 15, "Good News Network": 15,
    # Science
    "ScienceDaily": 17, "New Scientist": 16, "Inverse": 16,
    # Business
    "WSJ": 17,
}

CATEGORY_BONUS = {
    "world": 12, "sports": 11, "entertainment": 11,
    "tech": 10, "science": 10, "psychology": 11,
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
3. The landing — chosen by story diagnosis (see below)

STYLE RULES:
- Write like someone talking, not writing
- Casual American English: contractions, imperfect punctuation fine
- CONTRACTIONS ARE DEFAULT: always use I'm, we're, it's, don't, can't, isn't,
  they're, you're, I've, I'd, that's, there's, won't
  Exception: full form allowed ONLY when a real American would stress it aloud for emphasis
  Test: say it out loud. If stressing the full word sounds natural in speech → allowed.
  If it just sounds stiff → use the contraction.
  Allowed: "I am done." (said through gritted teeth) / "We are not doing this." (firm refusal)
  NOT allowed: "I am just here waiting" / "I cannot even get my printer" ← must be I'm / I can't
- Capitalize the first word of the post and the pronoun "I" always
- ALL CAPS allowed for a single word only when emphasis is genuinely needed (e.g. "we have FEELINGS")
- Natural spoken phrases: "ok but", "wait", "honestly", "I mean", "at this point",
  "sure", "right?", "wild", "no but seriously"
- NEVER use: "lol", "ngl", "tbh" — those are typed, not spoken
- No hashtags. No emojis. No URLs in the post.
- Dark humor OK if it punches UP at power/institutions — never at victims
- Sensitive topics OK: sex (as humor/observation, not explicit), politics (irony not partisan),
  mental health (relatable not clinical)
- The landing should make people want to reply WITHOUT asking them to
- Target 120-180 characters total. Never exceed 240. Cut ruthlessly — shorter is almost always funnier.
- Use numerals and abbreviations: $40B not "forty billion", 3pm not "three pm"
- Use "..." to let a thought trail off when the reader should fill in the rest
- Omit the period on the landing line when you want it to feel unfinished
- Use a period on the landing line when you want it to feel definitive and cut off
- Never use ".." (two dots) — looks like a typo. Never use "!" — kills the dry humor
- Always use real names: OpenAI not "a tech company", Starbucks not "a coffee chain"
- Use "we" only when the subject is humanity, society, or the reader as a consumer
  Test: could you replace "we" with "humans" or "people like us"? If yes → use "we".
  If no → use the actual subject (OpenAI, the government, they)
  Correct: "We built this." / "We have feelings." / "We're paying for it."
  Wrong: "We bombed Lebanon." / "We raised interest rates." ← use the actual subject

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THE LANDING LINE — diagnose the story first, then choose
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before writing the landing, ask: what is the PRIMARY energy this story carries?
Choose the landing type that matches. If a story doesn't qualify for a type, use a different type.
Never force a type that doesn't fit — rewrite the body until one qualifies naturally.

TYPE A — Instant laugh
USE WHEN: the story is surprising, absurd, or counterintuitive as a plain fact
THE MOVE: land before the reader sees it coming. Under 6 words. Works spoken aloud on a stage.
Examples: "Color me surprised." / "Respect the commitment." / "Nobody asked."
SKIP IF: the absurdity needs explaining to land, or you've already used this exact phrase in the batch

TYPE B — Delayed laugh
USE WHEN: the irony lives in the gap between two things
(what was said vs. what was done / what was promised vs. what happened / scale vs. outcome)
THE MOVE: leave the most important word unsaid. The gap between what you said and what you meant — that's the laugh.
Examples: "Meanwhile my laptop." / "I just wanted a sandwich." / "It has never met me."
SKIP IF: the gap isn't immediately obvious without context, or the pivot feels random

TYPE C — The sharp read
USE WHEN: power, institutions, or money are doing something obviously wrong but presented as normal
THE MOVE: say the one true thing nobody in the room is saying. Must be specific to THIS story.
Under 12 words. No hedging. No "maybe" or "kind of". Feels like the smartest person finally speaking.
Examples:
"The safety team left before the launch. Just so you know."
"The press release and the product are different documents."
"They announced the layoffs on the same slide as the record profits."
SKIP IF: the observation could apply to any story this week — generic cynicism is noise, not a read

TYPE D — Pivot to self
USE WHEN: the story reveals a universal behavior, feeling, or situation that's rarely named out loud
THE MOVE: drop the news entirely. Land on the human experience it exposes.
The reader should feel seen, not informed. This is recognition, not a joke — the laugh comes from being seen.
Examples:
"I've been doing this for years and nobody gave me a term for it."
"Anyway I have a meeting in 4 minutes."
"I just wanted to be normal about it."
SKIP IF: the pivot requires the news to make sense, or the universal experience feels like a stretch

OVERRIDE RULES — apply after diagnosis:
- If no type passes its own SKIP test → rewrite the body until one does
- If two types both qualify → choose the one with the shorter landing
- NEVER use the exact same landing phrase twice in one batch — not even close variants
- ONE punchline per post — if you have two jokes, cut the weaker one before writing the landing
- The landing must connect to THIS story — a reader who only sees the landing should guess the topic
- The landing must sound like something a real American would say out loud to a friend
  If it only works written — rewrite it

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STORY SELECTION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ENTERTAINMENT:
Ask: "Would someone interrupt their friend mid-sentence to share this?"
If yes — pick it.
SKIP: box office numbers, ratings data, casting news alone, production updates alone
PICK: massive franchise moments, shocking personal news, nostalgia triggers,
something everyone has an opinion on

POLITICS / WORLD NEWS:
Skip straight reporting. Pick only when the irony is self-evident —
when the gap between what was said and what's true is the whole joke.
The story must work without explaining the politics.
SKIP: policy announcements, summit results, vote counts
PICK: a leader contradicting their own stated position, a statement that aged badly within 24 hours,
power doing something absurd in plain sight

BUZZ SCORE CRITERIA:
90-100: Will spark strong opinions, "same" replies, or debates
70-89: Funny and relatable, will get likes and reposts
50-69: Interesting but niche audience
below 50: Skip this story

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
      "landing_type": "<A|B|C|D>",
      "post": "<120-240 chars, no URL, follow all style rules above>"
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
        story        = candidates[idx]
        post_raw     = sel.get("post", "").strip()
        landing_type = sel.get("landing_type", "?")
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
            "landing_type":   landing_type,
        })
        print(f"  [Scorer] Selected [{story['category']}] {story['title'][:60]}...")
        print(f"           Type: {landing_type} | Post: {post_raw[:80]}...")

    # 持ち越し候補保存（選ばれなかった上位8件）
    rejected = [c for i, c in enumerate(candidates) if i not in selected_indices]
    rejected_sorted = sorted(rejected, key=lambda x: x.get("rule_score", 0), reverse=True)
    save_carryover(state, rejected_sorted)

    print(f"\n[Scorer] Generated {len(output)}/{POSTS_PER_COLLECTION} posts")
    return output
