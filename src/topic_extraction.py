"""Topic extraction: turn a post into a small list of topics.

Two simple, reproducible methods:
  * hashtag  - topics are hashtags (from a hashtag column and/or '#tags' inside the text)
  * keyword  - topics are meaningful words in the text (stop-words removed)

This is plain string matching. It does NOT understand meaning (synonyms, sarcasm, context),
so it is a limitation that should be stated in the report.
"""
import ast
import json
import re
import unicodedata

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"@\w+")
HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)
WORD_RE = re.compile(r"[a-z][a-z']+")

STOPWORDS = set("""
a about above after again against all also am an and any are aren't as at be because been before being below
between both but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each few
for from further get got had hadn't has hasn't have haven't having he her here hers herself him himself his how
i i'd i'll i'm i've if in into is isn't it it's its itself just let's like me more most my myself no nor not now
of off on once only or other ought our ours ourselves out over own really same she should shouldn't so some such
than that that's the their theirs them themselves then there there's these they they'd they'll they're they've
this those through to too under until up us very was wasn't we we'd we'll we're we've were weren't what what's
when where which while who whom why will with won't would wouldn't you you'd you'll you're you've your yours
yourself yourselves amp rt via lol one two new today day got going know want see time good love people make
""".split())


def normalise_hashtag(tag, min_length: int = 2):
    """'#BlackFriday!' -> 'blackfriday'. Returns None for unusable tags (too short, only digits)."""
    if tag is None:
        return None
    text = unicodedata.normalize("NFKC", str(tag)).lower().strip().strip("'\"")
    text = re.sub(r"[^\w]", "", text, flags=re.UNICODE)
    if len(text) < min_length or text.isdigit():
        return None
    return text


def parse_hashtag_field(value, min_length: int = 2) -> list:
    """Understand common hashtag column formats: list, "['a','b']", "#a #b", "a,b", JSON text."""
    if value is None:
        return []
    if isinstance(value, float) and value != value:  # NaN
        return []
    items = []
    if isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        text = str(value).strip()
        if not text or text.lower() in ("nan", "none", "null", "[]"):
            return []
        if text.startswith("["):
            parsed = None
            for loader in (json.loads, ast.literal_eval):
                try:
                    parsed = loader(text)
                    break
                except (ValueError, SyntaxError):
                    continue
            items = list(parsed) if isinstance(parsed, (list, tuple)) else re.split(r"[\s,;|]+", text.strip("[]"))
        else:
            items = re.split(r"[\s,;|]+", text)
    cleaned = []
    for item in items:
        if isinstance(item, dict):  # e.g. Twitter entities {"text": "tag"}
            item = item.get("text") or item.get("tag")
        tag = normalise_hashtag(item, min_length)
        if tag:
            cleaned.append(tag)
    return cleaned


def extract_hashtags_from_text(text, min_length: int = 2) -> list:
    if not text:
        return []
    found = (normalise_hashtag(match, min_length) for match in HASHTAG_RE.findall(str(text)))
    return [tag for tag in found if tag]


def extract_keywords(text, min_length: int = 4) -> list:
    """Meaningful lower-case words: URLs/@mentions/#hashtag symbols removed, stop-words dropped."""
    if not text:
        return []
    cleaned = URL_RE.sub(" ", str(text))
    cleaned = MENTION_RE.sub(" ", cleaned).replace("#", " ")
    cleaned = unicodedata.normalize("NFKC", cleaned).lower()
    words = (word.strip("'") for word in WORD_RE.findall(cleaned))
    return [w for w in words if len(w) >= min_length and w not in STOPWORDS]


def extract_topics(text, hashtag_value=None, mode: str = "hashtag", max_topics: int = 20) -> list:
    """Return the unique topics of ONE post (a post counts at most once per topic)."""
    if mode == "hashtag":
        topics = parse_hashtag_field(hashtag_value) + extract_hashtags_from_text(text)
    elif mode == "keyword":
        topics = extract_keywords(text)
    else:
        raise ValueError(f"Topic mode must be 'hashtag' or 'keyword' here, got '{mode}'")
    unique = list(dict.fromkeys(topics))  # keeps order, removes repeats
    return unique[:max_topics]
