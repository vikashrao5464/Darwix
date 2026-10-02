import asyncio
import logging
import re
from app.schemas.realtime import Candidate, SignalSelection

logger = logging.getLogger('darwix.realtime')
RULES = [
 ('compliance_risk', 'agent', r'guaranteed.{0,30}approv|approv.{0,30}guaranteed|no credit check|pasti disetujui|jamin.{0,20}disetujui', .97, 'high'),
 ('missed_opportunity', 'customer', r'another vehicle|second vehicle|another product|also need|kendaraan lain|isa pang', .90, 'medium'),
 ('rising_frustration', 'customer', r'frustrat|already told|explained.{0,15}(twice|three)|please listen|kesal|sudah bilang|nakakainis', .91, 'medium'),
 ('payment_difficulty', 'customer', r'cannot pay|can.t pay|struggling to pay|afford.{0,20}(not|cannot)|susah bayar|nggak bisa bayar|hirap.{0,15}bayad', .94, 'high'),
 ('callback_need', 'customer', r'call me back|call back later|callback|telepon.{0,15}lagi|ditelepon lagi|tawag.{0,15}ulit', .92, 'medium'),
 ('missed_opportunity', 'customer', r'maybe another option|not sure.{0,20}another', .55, 'low'),
]

class SignalDetector:
    def __init__(self, settings, llm):
        self.settings, self.llm = settings, llm
    async def detect(self, segment, recent):
        candidates = []
        for kind, role, expression, score, priority in RULES:
            if segment.speaker == role and re.search(expression, segment.text, re.I):
                if kind == 'compliance_risk' and re.search(r'not guaranteed|cannot guarantee|can.t guarantee|no guarantee', segment.text, re.I) and not re.search(r'no credit check',segment.text,re.I): continue
                if kind == 'callback_need' and re.search(r'do not call|don.t call|no callback',segment.text,re.I): continue
                if kind == 'missed_opportunity' and re.search(r'don.t need|do not need|no need',segment.text,re.I): continue
                candidates.append(Candidate(type=kind, confidence=score, evidence=segment.text[:500],
                                            speaker=role, priority=priority))
        if self.settings.realtime_llm_enabled:
            try:
                selected = await asyncio.wait_for(self.llm.classify_signals(recent), self.settings.provider_timeout_seconds)
                selected = SignalSelection.model_validate(selected)
                for candidate in selected.signals:
                    # Require literal evidence in this newly arrived segment and matching annotated role.
                    if candidate.speaker == segment.speaker and segment.speaker != 'unknown' and candidate.evidence in segment.text:
                        if not any(item.type == candidate.type for item in candidates): candidates.append(candidate)
            except Exception as exc:
                logger.warning('signal_provider_fallback', extra={'error_type':type(exc).__name__})
        return candidates
