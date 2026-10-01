import re
from dataclasses import dataclass


@dataclass
class PIIResult:
    contains_pii: bool
    redacted_text: str


def redact_pii(text: str, government_patterns=None) -> PIIResult:
    flagged = False

    def substitute(pattern, marker, protect_amounts=False):
        nonlocal text, flagged
        def replace(match):
            nonlocal flagged
            prefix = text[max(0, match.start() - 40):match.start()]
            if protect_amounts and re.search(r"(?:INR|PHP|IDR|USD|Rs\.?|[$₹₱]|amount|turnover|revenue|premium|limit)\s*[:=]?\s*$", prefix, re.I):
                return match[0]
            flagged = True
            return marker
        text = re.sub(pattern, replace, text, flags=re.I)

    substitute(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", "[EMAIL_REDACTED]")
    # Long sequences first: a 16-digit card must not leave a 4-digit tail
    # after a shorter government-ID pattern matches its first twelve digits.
    substitute(r"(?<!\w)\d(?:[ -]?\d){12,}(?!\w)", "[ACCOUNT_REDACTED]", True)
    patterns = government_patterns if government_patterns is not None else [r"\b\d{3}-\d{2}-\d{4}\b", r"\b\d{4} \d{4} \d{4}\b"]
    for pattern in patterns:
        substitute(pattern, "[GOV_ID_REDACTED]")
    substitute(r"(?<!\w)(?:\+\d{1,3}[ -]?)?(?:\(\d{2,4}\)[ -]?\d(?:[ -]?\d){6,9}|\d(?:[ -]?\d){9,11})(?!\w)", "[PHONE_REDACTED]", True)
    return PIIResult(flagged, text)
