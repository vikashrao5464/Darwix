import re

from app.schemas.voice import InterpretedTurn

NUMBER_WORDS = {"zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,
                "ten":10,"eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,"seventeen":17,
                "eighteen":18,"nineteen":19,"twenty":20,"thirty":30,"forty":40,"fifty":50,"sixty":60,"seventy":70,"eighty":80,"ninety":90}
MULTIPLIERS = {"hundred":100,"thousand":1000,"lakh":100000,"lakhs":100000,"lac":100000,"lacs":100000,"million":1000000,"crore":10000000}


def parse_number(text):
    if re.search(r"(?<!\w)-\s*\d|\b(?:minus|negative|half|quarter)\b", text, re.I):
        return None
    normalized = re.sub(r"(?<=\d),(?=\d)", "", text.casefold()).replace("-", " ")
    words = re.findall(r"\d+(?:\.\d+)?|[a-z]+", normalized)
    groups, value, total, found = [], 0, 0, False
    for word in words + ["END"]:
        if re.fullmatch(r"\d+(?:\.\d+)?", word):
            if found:
                groups.append(total + value)
                value, total = 0, 0
            value, found = float(word), True
        elif word in NUMBER_WORDS:
            value += NUMBER_WORDS[word]
            found = True
        elif word in MULTIPLIERS and found:
            multiplier = MULTIPLIERS[word]
            if multiplier == 100:
                value *= multiplier
            else:
                total += value * multiplier
                value = 0
        elif word == "and" and found:
            continue
        else:
            if found:
                groups.append(total + value)
            value, total, found = 0, 0, False
    # A range or multiple amounts is ambiguous, not a guessed midpoint.
    if len(groups) != 1:
        return None
    number = groups[0]
    return int(number) if int(number) == number else number


def yes_no(text):
    text = text.casefold().strip(" .!?")
    if re.fullmatch(r"(?:yes|yeah|yep|sure|correct|confirmed|i agree|i consent|yes,? i consent|yes please|yes i do|i do)", text):
        return True
    if re.fullmatch(r"(?:no|nope|no thanks|no thank you|i do not|i don't|none|no i do not|no i don't)", text):
        return False
    return None


def field_value(field, text):
    if re.search(r"\b(?:unknown|do not know|don't know|cannot remember|can't remember)\b", text, re.I):
        return None
    if field in {"requested_amount", "annual_turnover", "business_age_months"}:
        number = parse_number(text)
        if number is None:
            return None
        if field == "business_age_months":
            if re.search(r"\byears?\b", text, re.I):
                number *= 12
            elif not re.search(r"\bmonths?\b", text, re.I):
                return None
            if number != int(number):
                return None
            return int(number)
        return number
    if field in {"existing_loan", "callback_preference"}:
        answer = yes_no(text)
        if answer is not None:
            return answer
        if field == "existing_loan":
            if re.search(r"\b(?:no existing loan|do not have.*loan|don't have.*loan|no loan)\b", text, re.I):
                return False
            if re.search(r"\b(?:have an? existing loan|have an? loan|already have.*loan)\b", text, re.I):
                return True
        return None
    if field == "city":
        match = re.search(r"\b(?:in|city is|located in|based in)\s+([a-zA-Z ]+?)[.!?]*$", text, re.I)
        return match[1].strip() if match else text.strip(" .!?")
    if field == "business_type":
        match = re.search(r"\b(?:run|operate|own|business is)\s+(?:an?\s+)?([a-zA-Z ]+?)[.!?]*$", text, re.I)
        return match[1].strip() if match else text.strip(" .!?")
    return None


def interpret_local(text, pending_field):
    lower = text.casefold()
    intent, field = "details", None
    if re.search(r"\b(?:human|representative|real person|agent|someone to help)\b", lower):
        intent = "escalation"
    elif re.search(r"\b(?:stop|end the call|goodbye|withdraw consent)\b", lower):
        intent = "end"
    elif re.search(r"\b(?:create|save).*(?:lead|application)\b", lower):
        intent = "create_lead"
    elif re.search(r"\b(?:call me back|callback|call back)\b", lower) and pending_field != "callback_preference":
        intent = "callback"
    elif re.search(r"\b(?:what|why|how|can|could|tell me|explain|fees?|rates?|documents?|approval|requirement|cashback)\b", lower) or "?" in text:
        intent = "faq"
    else:
        for key, pattern in (
            ("business_age_months", r"\b(?:business age|operating|operated|open for|months?|years?)\b"),
            ("annual_turnover", r"\b(?:turnover|annual sales|annual revenue)\b"),
            ("requested_amount", r"\b(?:amount|borrow|request|loan of)\b"),
            ("existing_loan", r"\b(?:existing loan|already have.*loan|no loan)\b"),
            ("city", r"\b(?:city|located|based in)\b"),
            ("business_type", r"\b(?:retail|manufacturing|business is|operate|shop)\b"),
        ):
            if re.search(pattern, lower):
                field = key
                break
        field = field or pending_field
        if field is None:
            intent = "unknown"
    return InterpretedTurn(intent=intent, field=field if intent == "details" else None,
        evidence=text if intent == "details" and field else None, uncertain=bool(re.search(r"\b(?:maybe|about|approximately|not sure|i think|around)\b", lower)))
