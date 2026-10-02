import asyncio

class EventHub:
    def __init__(self, max_subscribers=8):
        self.subscribers=set()
        self.limit=max_subscribers
    def subscribe(self):
        if len(self.subscribers) >= self.limit: raise RuntimeError('subscriber_limit')
        queue=asyncio.Queue(maxsize=128)
        self.subscribers.add(queue)
        return queue
    def unsubscribe(self, queue): self.subscribers.discard(queue)
    def disconnect_all(self, reason):
        for queue in tuple(self.subscribers):
            while not queue.empty(): queue.get_nowait()
            queue.put_nowait({'type':'disconnect','payload':{'reason':reason}})
        self.subscribers.clear()
    async def publish(self, kind, payload):
        event={'type':kind,'payload':payload}
        for queue in tuple(self.subscribers):
            if queue.full():
                self.unsubscribe(queue)
                # Wake the slow sender and close that connection explicitly.
                while not queue.empty(): queue.get_nowait()
                queue.put_nowait({'type':'disconnect','payload':{'reason':'subscriber_too_slow'}})
            else: queue.put_nowait(event)
