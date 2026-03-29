import json
import time
from google import genai

from config import GEMINI_API_KEY, GEMINI_MODEL, BUZZ_THRESHOLD, CATEGORY_COLORS

client = genai.Client(api_key=GEMINI_API_KEY)

PROMPT = """You are a globally viral Twitter account. Analyze this story and respond ONLY with valid JSON.

Story:
  Title:    {title}
  Summary:  {summary}
  Source:   {source}
  Category: {category}

Respond ONLY with this JSON (no markdown, no explanation):
{{
  "buzz_score": <0-100 integer>,
  "verdict": "<one sentence why it will or won't go viral>",
  "main_tweet": "<EXACTLY under 100 chars. Punchy summary. No hashtags. Start with strong hook.>",
  "sub_tweet": "<EXACTLY under 100 chars. Witty/humorous/dark-humorous opinion OR smart advice OR hot take. Compliant. No hashtags.>",
  "headline": "<short image headline, max 8 words>",
  "simple_explanation": "<explain to a curious 10-year-old in 2-3 clear sentences. Use simple words. Make it exciting.>",
  "emoji": "<single most relevant emoji>",
  "color_hex": "<hex color matching the mood, e.g. #C0392B for breaking news>"
}}

Scoring (0-100):
- Surprise/shock factor       (0-25)
- Global audience appeal      (0-25)  
- Shareability / reaction fuel (0-25)
- Timeliness                  (0-25)

Rules:
- main_tweet MUST be under 100 characters including spaces. Count carefully.
- sub_tweet MUST be under 100 characters including spaces. Count carefully.
- sub_tweet must add value: humor, insight, or a clever hot take — NOT just a repeat of main_tweet.
- No slurs, no hate speech, no explicit content. Dark humor is OK if non-discriminatory.
"""


def score_story(story: dict) -> dict | None:
    prompt = PROMPT.format(
        title    = story["title"][:200],
        summary  = story["summary"][:400],
        source   = story["source"],
        category = story["category"],
    )
    try:
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        raw   = response.text.strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON")
        result = json.loads(raw[start:end])

        result["buzz_score"] = min(100, result.get("buzz_score", 0) + min(4, story.get("weight", 5) - 5))
        result["original_title"] = story["title"]
        result["url"]            = story["url"]
        result["source"]         = story["source"]
        result["category"]       = story["category"]

        mt = result.get("main_tweet", "")
        st = result.get("sub_tweet", "")
        result["main_tweet"] = mt[:100].strip()
        result["sub_tweet"]  = st[:100].strip()

        if not result.get("color_hex"):
            result["color_hex"] = CATEGORY_COLORS.get(story["category"], "#2C3E50")

        return result

    except json.JSONDecodeError as e:
        print(f"    [Scorer] JSON error: {e}")
        return None
    except Exception as e:
        print(f"    [Scorer] API error: {e}")
        return None


def score_all(stories: list[dict]) -> list[dict]:
    candidates = []
    discarded  = 0

    print(f"\n[Scorer] Scoring {len(stories)} stories (threshold: {BUZZ_THRESHOLD})\n")

    for i, story in enumerate(stories, 1):
        print(f"  [{i:>3}/{len(stories)}] {story['title'][:60]}...")
        result = score_story(story)

        if result is None:
            discarded += 1
            print("           → ERROR")
            time.sleep(5)
            continue

        score = result.get("buzz_score", 0)
        if score >= BUZZ_THRESHOLD and result.get("main_tweet") and result.get("sub_tweet"):
            candidates.append(result)
            print(f"           → PASS  {score}/100  [{story['category']}]")
        else:
            discarded += 1
            print(f"           → SKIP  {score}/100")

        time.sleep(4.2)   # 15 req/min = 4s間隔

    candidates.sort(key=lambda x: x.get("buzz_score", 0), reverse=True)
    print(f"\n[Scorer] Passed: {len(candidates)}  Discarded: {discarded}")
    return candidates
