import redis
import json
import os

REDIS_URL = os.getenv("REDIS_URL")

redis_client = redis.from_url(REDIS_URL, decode_responses=True, ssl=True)


def set_session(broker_id, data, ttl = 600):
    redis_client.setex(f"session:{broker_id}", ttl, json.dumps(data))

def get_session(broker_id):
    val = redis_client.get(f"session:{broker_id}")
    return json.loads(val) if val else None

def clear_session(broker_id):
    redis_client.delete(f"session:{broker_id}")