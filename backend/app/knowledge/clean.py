import re
import unicodedata
from collections import Counter
from datetime import datetime


NAVIGATION_LINES = {"home", "menu", "login", "log in", "privacy policy", "cookie settings", "back to top", "next", "previous"}
STOP_WORDS = set("a an the is are be can could would should do does did how what which when where who why i my me you your we our of for from to in on at by with and or as it this that have has must any please tell about business loan demo synthetic not apply application available information only under into need".split())


def normalize_terms(text: str, terminology: dict[str, str]):
    for original, replacement in sorted(terminology.items(), key=lambda item: -len(item[0])):
        text = re.sub(r"(?<!\w)" + re.escape(original) + r"(?!\w)", replacement, text, flags=re.I)
    return text


def normalize_dates(text: str):
    def convert(match):
        raw = match[0]
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(raw, fmt).date().isoformat()
            except ValueError:
                pass
        return raw
    return re.sub(r"\b(?:\d{1,2}[/\-]\d{1,2}[/\-]\d{4}|\d{1,2} [A-Za-z]+ \d{4})\b", convert, text)


def clean_text(text, terminology=None, repeated_lines=None):
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n")
    lines = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line.casefold() in NAVIGATION_LINES or line in (repeated_lines or set()):
            continue
        if re.fullmatch(r"(?:page\s+)?\d+\s*(?:of|/)\s*\d+", line, re.I):
            continue
        line = re.sub(r"^[•▪●*]\s*", "- ", line)
        line = re.sub(r"^#{1,6}\s*", "", line)
        lines.append(line)
    return normalize_terms(normalize_dates("\n".join(lines)), terminology or {})


def clean_units(units, terminology):
    counts = Counter()
    for unit in units:
        lines = [re.sub(r"\s+", " ", line).strip() for line in unit.text.splitlines() if line.strip()]
        edge_lines = set(lines[:1] + lines[-1:])
        counts.update(line for line in edge_lines if len(line) < 100)
    repeated = {line for line, count in counts.items() if count >= 2}
    return [u.model_copy(update={"text": clean_text(u.text, terminology, repeated)}) for u in units]


def query_tokens(text, terminology=None):
    normalized = normalize_terms(unicodedata.normalize("NFKC", text).casefold(), terminology or {})
    words = re.findall(r"[a-z0-9]+", normalized)
    return [word[:-1] if word.endswith("s") and len(word) > 4 else word
            for word in words if word not in STOP_WORDS and len(word) > 1]
