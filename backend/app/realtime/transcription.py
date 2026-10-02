from collections import deque

class RollingTranscript:
    def __init__(self, seconds=45):
        self.window_ms = seconds * 1000
        self.segments = deque(maxlen=40)
    def add(self, segment):
        self.segments.append(segment)
        while self.segments and self.segments[0].end_ms < segment.end_ms - self.window_ms:
            self.segments.popleft()
    def context(self):
        return [segment.model_dump() for segment in self.segments]
