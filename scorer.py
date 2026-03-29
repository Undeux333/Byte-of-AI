import json
import time
from google import genai

from config import GEMINI_API_KEY, GEMINI_MODEL, BUZZ_THRESHOLD, CATEGORY_COLORS

client = genai.Client(api_key=GEMINI_API_KEY)

PROMPT = """You are a viral American Twitter account run by a witty, culturally fluent US native.
All output MUST be written in natural, casual American English — the way a sharp 25-35 year old American would actually type on Twitter.
Never use British spelling (colour → color, realise → realize, etc.).
Never sound translated, formal, or robotic. Sound human, punchy, and American.

Analyze this story and respond ONLY with valid JSON (no markdown, no explanation):

Story:
  Title:    {title}
  Summary:  {summary}
  Source:   {source}
  Category: {category}

Respond ONLY with this exact JSON:
{{
  "buzz_score": <0-100 integer>,
  "verdict": "<one sentence why it will or won't go viral>",
  "main_tweet": "<EXACTLY under 100 chars. Written like a sharp American tweeter. No hashtags. Hook first. American spelling and slang OK.>",
  "sub_tweet": "<EXACTLY under 100 chars. Add a witty/dark-humorous American take, hot opinion, or actionable advice. Must feel like a real American person's reaction — not a press release. No hashtags.>",
  "headline": "<8 words max. Punchy American headline style — like a bold NYT or BuzzFeed headline.>",
  "simple_explanation": "<Explain to a curious American 10-year-old in 2-3 sentences. Use everyday American words. Make it exciting and easy to picture. No jargon.>",
  "emoji": "<single most fitting emoji>",
  "color_hex": "<hex color matching the mood, e.g. #C0392B for breaking news>"
}}

Scoring rubric (total 0-100):
- Surprise / shock factor for a US audience   (0-25)
- Global + American appeal                     (0-25)
- Shareability / reaction fuel on US Twitter   (0-25)
- Timeliness and relevance right now           (0-25)

Hard rules:
- main_tweet: strictly under 100 characters including spaces. Count every character.
- sub_tweet: strictly under 100 characters including spaces. Count every character.
- sub_tweet must NOT repeat the main_tweet. It should add a new angle — humor, a hot take, or advice.
- Dark humor is OK if it punches up, not down. No slurs, no hate speech, no explicit content.
- American English only: contractions (it's, don't, gonna, wanna), casual phrasing, American cultural references.
- simple_explanation must use American vocabulary (like "soccer" not "football", "apartment" not "flat").
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

        result["main_tweet"] = result.get("main_tweet", "")[:100].strip()
        result["sub_tweet"]  = result.get("sub_tweet", "")[:100].strip()

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
