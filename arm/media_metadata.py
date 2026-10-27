"""Title normalization and conservative disc-label parsing."""
import re

try:
    import wordninja
except ImportError:  # optional; keep ARM usable without extra packages
    wordninja = None


_TITLE_WORDS = set("""
a an academia and anime are at back bad batman beauty big black blade breaking
brothers by call captain castle charlie chicago chronicles city cloud code cold
criminal dark dawn day dead death demon detective doctor dragon dream earth east
edge empire end eternal every evil family fantastic fast fear fight final finding
fire first flash flower for forest found friends frozen full galaxy game games
gang ghost girl glass god good gone golden green grey guardians hack halloween
harry heart hell hero heroes history hobbit holmes home house how ice inception
indiana inside iron island jack james john joker jump jurassic justice king kings
knight kung lake last league legend legends life little lord lost love mad magic
man matrix men midnight mission modern money moon murder music mystic my name
national natural new night north notes ocean office old once one orange order
origin pacific park part people perfect planet police potter power princess
prison private project pursuit queen quiet race raiders rangers red resident
return rising river road rock rocky rogue roman room royal run running rush
samurai saving scarface school science scream sea secret sense serial series
seven shadow shadows shark sherlock show silent silver sin sister sky slow small
snow social solar soldier south space special spider spirit star stars start
state station stranger street suicide super superman survival sweet tales tale
tank teen terminator the thing things thor time titan titanic tom top toy train
transformers treasure true twilight unknown up us vacation v for virginia walking
war wars water way west white who wild winter witch wizard wolf woman wonder
world year young zero zone
""".split())


# Common filesystem labels that are not useful metadata search terms.
_GENERIC_DISC_TITLES = {
    "", "undefined", "unknown", "not identified", "unidentified", "untitled",
    "none", "null", "n a", "na", "video", "videos", "dvd", "dvd video",
    "video dvd", "video ts", "audio ts", "blu ray", "bluray", "bd video",
    "disc", "disk", "disc title", "disk title", "title", "movie", "film",
    "data", "data disc", "volume", "track", "no title", "no name",
    "default", "generic", "new volume", "isoimage", "iso image",
}


def is_generic_disc_title(value):
    """Return True when a disc label is too generic for metadata lookup."""
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    normalized = re.sub(r"\\s+", " ", normalized)
    if normalized in _GENERIC_DISC_TITLES:
        return True
    return bool(re.fullmatch(
        r"(?:dvd|video|disc|disk|title|volume|track|movie|film)(?:\\s+(?:\\d+|[a-z]))?",
        normalized,
    ))


def _fallback_split_compound(value):
    """Split compact titles only if all parts form a known-word segmentation."""
    value = re.sub(r"[^a-z]", "", str(value).lower())
    if len(value) < 7:
        return []
    best = [None] * (len(value) + 1)
    best[len(value)] = (0, [])
    for start in range(len(value) - 1, -1, -1):
        for end in range(start + 2, min(len(value), start + 20) + 1):
            token, tail = value[start:end], best[end]
            if token in _TITLE_WORDS and tail is not None:
                score = len(token) * len(token) + tail[0] - 3
                if best[start] is None or score > best[start][0]:
                    best[start] = (score, [token] + tail[1])
    if best[0] and len(best[0][1]) > 1:
        return best[0][1]
    return []


def title_search_variants(title):
    """Produce ordered, distinct query variants for joined-word disc labels."""
    raw = str(title or "").strip()
    if not raw or is_generic_disc_title(raw):
        return []
    normalized = re.sub(r"[_+]+", " ", raw)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    variants = []

    def add(value):
        value = re.sub(r"\s+", " ", str(value or "")).strip()
        if value and value.casefold() not in {v.casefold() for v in variants}:
            variants.append(value)

    add(normalized)
    camel = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", normalized)
    camel = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", camel)
    add(camel)
    compact = re.sub(r"[^A-Za-z]", "", normalized)
    if " " not in normalized and len(compact) >= 7:
        words = []
        if wordninja is not None:
            try:
                words = wordninja.split(compact.lower())
            except Exception:
                words = []
        if not words or len(words) < 2:
            words = _fallback_split_compound(compact)
        if len(words) > 1:
            add(" ".join(words))
    return variants[:3]


def safe_positive_int(value, maximum=999):
    """Convert to a bounded positive integer, returning None for invalid/empty data."""
    if value is None or str(value).strip() == "":
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= maximum else None


def detect_disc_metadata(*values):
    """Detect season, disc and episode values only from explicit label conventions."""
    text = " ".join(str(value) for value in values if value not in (None, ""))
    text = text.replace("_", " ").replace(".", " ")
    result = {"season_number": None, "disc_number": None,
              "episode_start": None, "episode_end": None}
    season_episode = re.search(
        r"\bS\s*0*(\d{1,2})\s*E\s*0*(\d{1,3})"
        r"(?:\s*(?:-|–|—|to|through|&|and)\s*E?\s*0*(\d{1,3}))?\b",
        text, re.IGNORECASE
    )
    if season_episode:
        result["season_number"] = safe_positive_int(season_episode.group(1), 99)
        result["episode_start"] = safe_positive_int(season_episode.group(2))
        result["episode_end"] = safe_positive_int(season_episode.group(3) or season_episode.group(2))
    else:
        season = re.search(r"\b(?:season|series)\s*#?\s*0*(\d{1,2})\b", text, re.IGNORECASE)
        if not season:
            season = re.search(r"\bS\s*0*(\d{1,2})(?=\s*(?:$|[\s_-]|disc|disk|d\d))",
                               text, re.IGNORECASE)
        if season:
            result["season_number"] = safe_positive_int(season.group(1), 99)
        episode_range = re.search(
            r"\b(?:episodes?|eps?|ep|e)\s*0*(\d{1,3})\s*"
            r"(?:-|–|—|to|through|&|and)\s*"
            r"(?:(?:episodes?|eps?|ep|e)\s*)?0*(\d{1,3})\b", text, re.IGNORECASE
        )
        if episode_range:
            result["episode_start"] = safe_positive_int(episode_range.group(1))
            result["episode_end"] = safe_positive_int(episode_range.group(2))
        else:
            single = re.search(r"\bepisode\s*#?\s*0*(\d{1,3})\b", text, re.IGNORECASE)
            if single:
                result["episode_start"] = safe_positive_int(single.group(1))
                result["episode_end"] = result["episode_start"]

    disc = re.search(r"\b(?:disc|disk)\s*#?\s*0*(\d{1,2})\b", text, re.IGNORECASE)
    if not disc:
        disc = re.search(r"\bD\s*0*(\d{1,2})\b", text, re.IGNORECASE)
    if disc:
        result["disc_number"] = safe_positive_int(disc.group(1), 99)
    if result["episode_start"] and result["episode_end"] and result["episode_end"] < result["episode_start"]:
        result["episode_start"], result["episode_end"] = result["episode_end"], result["episode_start"]
    return result


def select_best_media_result(results, title=None, year=None, prefer_series=False):
    """Prefer exact title/year matches and respect explicit TV episode metadata."""
    candidates = list(results or [])
    if not candidates:
        return None

    def normalized(value):
        return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())

    exact_title = [
        item for item in candidates
        if normalized(item.get("Title") or item.get("title") or item.get("name")) == normalized(title)
    ] if title else []
    pool = exact_title or candidates
    if year:
        year_matches = [
            item for item in pool
            if str(item.get("Year") or "")[:4] == str(year)[:4]
        ]
        if year_matches:
            pool = year_matches

    if prefer_series:
        series = [item for item in pool if str(item.get("Type", "")).lower() in ("series", "tv")]
        if not series:
            series = [item for item in candidates if str(item.get("Type", "")).lower() in ("series", "tv")]
        if series:
            return series[0]
    return pool[0]


def parse_media_label(label):
    """Parse title/year/disc data present in a label without inventing missing metadata."""
    raw = str(label or "").strip()
    result = {"title": "", "year": None, **detect_disc_metadata(raw)}
    if not raw:
        return result
    working = re.sub(r"\s+", " ", raw.replace("_", " ").replace("+", " ")).strip()
    year_match = re.search(r"(?<!\d)(?:18\d{2}|19\d{2}|20\d{2})(?!\d)", working)
    if year_match:
        result["year"] = year_match.group(0)
        working = working[:year_match.start()] + " " + working[year_match.end():]

    patterns = (
        r"\bS\s*0*\d{1,2}\s*E\s*0*\d{1,3}(?:\s*(?:-|–|—|to|through|&|and)\s*E?\s*0*\d{1,3})?\b",
        r"\b(?:season|series)\s*#?\s*0*\d{1,2}\b",
        r"\b(?:disc|disk)\s*#?\s*0*\d{1,2}\b",
        r"\bD\s*0*\d{1,2}\b",
        r"\b(?:episodes?|eps?|ep|e)\s*0*\d{1,3}"
        r"(?:\s*(?:-|–|—|to|through|&|and)\s*"
        r"(?:(?:episodes?|eps?|ep|e)\s*)?0*\d{1,3})?\b",
    )
    for pattern in patterns:
        working = re.sub(pattern, " ", working, flags=re.IGNORECASE)
    working = re.sub(r"\b(?:DVD|BLU[- ]?RAY|PAL|NTSC|16X9)\b", " ", working, flags=re.IGNORECASE)
    working = re.sub(r"\bSKU\b.*$", " ", working, flags=re.IGNORECASE)
    working = re.sub(r"[\[\](){}]", " ", working)
    working = re.sub(r"[^A-Za-z0-9\s'-]", " ", working)
    working = re.sub(r"\s+", " ", working).strip(" -_.")
    if not working or is_generic_disc_title(working):
        return result
    variants = title_search_variants(working)
    if " " not in working and len(variants) > 1:
        working = variants[-1]
    result["title"] = " ".join(
        token if token.isdigit() else token[0].upper() + token[1:].lower()
        for token in working.split()
    )
    return result
