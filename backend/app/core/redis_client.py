import redis
import logging
from app.core.config import settings

logger = logging.getLogger("redis_client")

_redis_instance = None

def get_redis_client():
    global _redis_instance
    if _redis_instance is not None:
        return _redis_instance
        
    if settings.REDIS_MOCK:
        import fakeredis
        logger.info("Using fakeredis for in-memory queue/cache operations")
        _redis_instance = fakeredis.FakeRedis(decode_responses=True)
        return _redis_instance

    try:
        client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        _redis_instance = client
        logger.info("Connected successfully to Redis server at %s", settings.REDIS_URL)
        return _redis_instance
    except Exception as e:
        logger.warning(f"Could not connect to Redis at {settings.REDIS_URL}: {e}. Falling back to FakeRedis.")
        import fakeredis
        _redis_instance = fakeredis.FakeRedis(decode_responses=True)
        return _redis_instance

class RedisQueue:
    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        self.client = get_redis_client()

    def enqueue(self, item_json: str) -> int:
        return self.client.rpush(self.queue_name, item_json)

    def dequeue(self, timeout: int = 1):
        # blocking pop or lpop
        res = self.client.blpop([self.queue_name], timeout=timeout)
        if res:
            return res[1]
        return None

    def length(self) -> int:
        return self.client.llen(self.queue_name)
