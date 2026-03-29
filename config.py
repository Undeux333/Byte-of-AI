import os

# ── API Keys (GitHub Secrets経由で自動注入) ───────────────────────────────
GEMINI_API_KEY            = os.getenv("GEMINI_API_KEY", "")
TWITTER_API_KEY           = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET        = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN      = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")

# ── Gemini ────────────────────────────────────────────────────────────────
GEMINI_MODEL   = "gemini-2.0-flash"
BUZZ_THRESHOLD = 68

# ── 収集間隔 ──────────────────────────────────────────────────────────────
COLLECTION_INTERVAL_HOURS = 2   # 2時間ごとに収集

# ── ファイル ──────────────────────────────────────────────────────────────
STATE_FILE = "data/state.json"
IMAGE_FILE = "data/card.png"

# ── ツイート ──────────────────────────────────────────────────────────────
MAX_TWEET_CHARS   = 100
MAX_SEEN_URLS     = 8000   # 重複チェック用URLの最大保持数
MAX_QUEUE_SIZE    = 60     # キューの最大件数

# ── カテゴリ別カラー (画像用) ─────────────────────────────────────────────
CATEGORY_COLORS = {
    "world":         "#C0392B",
    "tech":          "#2980B9",
    "entertainment": "#8E44AD",
    "sports":        "#27AE60",
    "science":       "#16A085",
    "business":      "#D35400",
    "other":         "#2C3E50",
}

# ── RSSソース (Twitterユーザー数上位国 × 全ジャンル) ──────────────────────
RSS_SOURCES = [
    # ── WORLD / POLITICS ─────────────────────────────────────────
    {"key": "reuters",      "name": "Reuters",       "url": "https://feeds.reuters.com/reuters/topNews",          "category": "world",   "weight": 9},
    {"key": "bbc_world",    "name": "BBC World",     "url": "http://feeds.bbci.co.uk/news/world/rss.xml",         "category": "world",   "weight": 9},
    {"key": "ap_top",       "name": "AP News",       "url": "https://feeds.apnews.com/rss/apf-topnews",           "category": "world",   "weight": 8},
    {"key": "aljazeera",    "name": "Al Jazeera",    "url": "https://www.aljazeera.com/xml/rss/all.xml",          "category": "world",   "weight": 7},
    {"key": "guardian",     "name": "The Guardian",  "url": "https://www.theguardian.com/world/rss",              "category": "world",   "weight": 7},
    # ── TECH ─────────────────────────────────────────────────────
    {"key": "techcrunch",   "name": "TechCrunch",    "url": "https://techcrunch.com/feed/",                       "category": "tech",    "weight": 8},
    {"key": "theverge",     "name": "The Verge",     "url": "https://www.theverge.com/rss/index.xml",             "category": "tech",    "weight": 8},
    {"key": "ars",          "name": "Ars Technica",  "url": "http://feeds.arstechnica.com/arstechnica/index",     "category": "tech",    "weight": 7},
    {"key": "wired",        "name": "Wired",         "url": "https://www.wired.com/feed/rss",                     "category": "tech",    "weight": 7},
    # ── ENTERTAINMENT ─────────────────────────────────────────────
    {"key": "variety",      "name": "Variety",       "url": "https://variety.com/feed/",                          "category": "entertainment", "weight": 8},
    {"key": "deadline",     "name": "Deadline",      "url": "https://deadline.com/feed/",                         "category": "entertainment", "weight": 7},
    {"key": "billboard",    "name": "Billboard",     "url": "https://www.billboard.com/feed/",                    "category": "entertainment", "weight": 7},
    # ── SPORTS ────────────────────────────────────────────────────
    {"key": "espn",         "name": "ESPN",          "url": "https://www.espn.com/espn/rss/news",                 "category": "sports",  "weight": 8},
    {"key": "bbc_sport",    "name": "BBC Sport",     "url": "http://feeds.bbci.co.uk/sport/rss.xml",              "category": "sports",  "weight": 7},
    # ── SCIENCE ───────────────────────────────────────────────────
    {"key": "sciencedaily", "name": "ScienceDaily",  "url": "https://www.sciencedaily.com/rss/top/science.xml",   "category": "science", "weight": 7},
    {"key": "newscientist", "name": "New Scientist", "url": "https://www.newscientist.com/feed/home/",            "category": "science", "weight": 7},
    # ── BUSINESS ──────────────────────────────────────────────────
    {"key": "cnn_biz",      "name": "CNN Business",  "url": "http://rss.cnn.com/rss/money_news_international.rss","category": "business","weight": 7},
]

# ── Redditサブレディット ───────────────────────────────────────────────────
REDDIT_SOURCES = [
    {"name": "worldnews",     "sort": "hot", "limit": 15, "min_ups": 3000, "category": "world"},
    {"name": "news",          "sort": "hot", "limit": 15, "min_ups": 2000, "category": "world"},
    {"name": "todayilearned", "sort": "hot", "limit": 15, "min_ups": 5000, "category": "other"},
    {"name": "technology",    "sort": "hot", "limit": 10, "min_ups": 1000, "category": "tech"},
    {"name": "movies",        "sort": "hot", "limit": 10, "min_ups": 1000, "category": "entertainment"},
    {"name": "sports",        "sort": "hot", "limit": 10, "min_ups": 1000, "category": "sports"},
    {"name": "science",       "sort": "hot", "limit": 10, "min_ups": 1000, "category": "science"},
    {"name": "entertainment", "sort": "hot", "limit": 10, "min_ups": 500,  "category": "entertainment"},
]

# ── HackerNews ────────────────────────────────────────────────────────────
HN_TOP_LIMIT = 25
HN_MIN_SCORE = 150
