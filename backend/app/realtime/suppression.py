import hashlib
import re
from app.realtime.nudges import ACTIONS

class Suppression:
    def __init__(self, settings):
        self.settings, self.last, self.fingerprints = settings, {}, {}
    def check(self, candidate, now):
        self.fingerprints = {key:until for key, until in self.fingerprints.items() if until > now}
        if candidate.confidence < self.settings.realtime_min_confidence: return 'low_confidence'
        normalized = re.sub(r'\W+', ' ', candidate.evidence.casefold()).strip()
        fingerprint = hashlib.sha256((candidate.type + normalized + ACTIONS[candidate.type][0]).encode()).hexdigest()
        if fingerprint in self.fingerprints: return 'duplicate'
        cooldown = self.settings.realtime_cooldowns.get(candidate.type, 30) * 1000
        if now - self.last.get(candidate.type, -float('inf')) < cooldown: return 'cooldown'
        self.last[candidate.type] = now
        self.fingerprints[fingerprint] = now + self.settings.realtime_duplicate_seconds * 1000
        return None
