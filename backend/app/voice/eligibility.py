import asyncio
import json
import logging
import re

from app.knowledge.citations import citation
from app.schemas.voice import EligibilityResult, EligibilityRule
from app.voice.qualification import CORE_FIELDS

logger = logging.getLogger("darwix.eligibility")


async def evaluate_eligibility(state, knowledge, settings):
    missing = [field for field in CORE_FIELDS if state.fields[field].status != "confirmed"]
    if any(state.fields[field].status == "conflicting" for field in CORE_FIELDS):
        return EligibilityResult(status="needs_human_review", missing_fields=missing,
            reasons=["Conflicting details must be confirmed before assessing preliminary qualification."])
    if missing:
        return EligibilityResult(status="incomplete", missing_fields=missing,
            reasons=["Missing or tentative details must be confirmed; no value was guessed."])
    try:
        config = json.loads(settings.qualification_rules_path.read_text(encoding="utf-8"))
        if config.get("synthetic") is not True or not config.get("rules"):
            raise ValueError("unverified_rule_configuration")
        rules = [EligibilityRule.model_validate(rule) for rule in config["rules"]]
        records = {r.record_id:r for r in await asyncio.wait_for(knowledge.index.records(), settings.provider_timeout_seconds)}
        results = []
        for rule in rules:
            record = records.get(rule.source_record_id)
            if not record or record.product != "business_loan" or record.version != rule.source_version or record.checksum != rule.source_checksum or not record.synthetic:
                raise ValueError("rule_source_unavailable_or_stale")
            if not rule.source_quote or rule.source_quote not in record.content:
                raise ValueError("rule_quote_unavailable")
            if rule.operator in {">=", "<="} and (type(rule.value) is not int or str(rule.value) not in re.findall(r"\d+", rule.source_quote)):
                raise ValueError("rule_threshold_not_in_evidence")
            if rule.operator == "in" and (not isinstance(rule.value, list) or not all(item in rule.source_quote for item in rule.value)):
                raise ValueError("rule_locations_not_in_evidence")
            if rule.operator == "review_if_true" and rule.value is not True:
                raise ValueError("invalid_review_rule")
            value = state.fields[rule.field].value
            if rule.operator == ">=":
                outcome = "pass" if value >= rule.value else "fail"
            elif rule.operator == "<=":
                outcome = "pass" if value <= rule.value else "fail"
            elif rule.operator == "in":
                outcome = "pass" if value.casefold() in [item.casefold() for item in rule.value] else "review"
            else:
                outcome = "review" if value is True else "pass"
            results.append({"rule_id":rule.rule_id, "field":rule.field, "outcome":outcome,
                "explanation":rule.explanation, "citation":citation(record).model_dump()})
        status = "not_preliminarily_qualified" if any(r["outcome"] == "fail" for r in results) else "needs_human_review" if any(r["outcome"] == "review" for r in results) else "preliminarily_qualified"
        return EligibilityResult(status=status, rules=results,
            reasons=[r["explanation"] for r in results if r["outcome"] != "pass"] or ["The confirmed details meet the synthetic preliminary rules. This is not final approval."])
    except Exception as exc:
        logger.warning("eligibility_evidence_unavailable", extra={"error_type":type(exc).__name__})
        return EligibilityResult(status="unavailable", reasons=["Verified qualification rules are unavailable or stale. A human must review eligibility."])
