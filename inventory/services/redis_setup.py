import redis
import json
import os

REDIS_URL = os.getenv("REDIS_URL")

redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def set_session(broker_id, data, ttl = 600):
    redis_client.setex(f"session:{broker_id}", ttl, json.dumps(data))

def get_session(broker_id):
    val = redis_client.get(f"session:{broker_id}")
    return json.loads(val) if val else None

def clear_session(broker_id):
    redis_client.delete(f"session:{broker_id}")

def mark_media_processed(media_id, ttl=86400):
    key = f"media_processed:{media_id}"
    redis_client.setex(key, ttl, "true")

def is_media_processed(media_id):
    key = f"media_processed:{media_id}"
    return redis_client.exists(key)

import json, time

def add_media_to_queue(broker_id, media_id):
    key = f"media_queue:{broker_id}"
    existing = redis_client.get(key)
    media_list = json.loads(existing) if existing else []
    media_list.append({"id": media_id, "ts": time.time()})
    redis_client.setex(key, 15, json.dumps(media_list))  # keep for 15s window

def pop_media_queue(broker_id):
    key = f"media_queue:{broker_id}"
    existing = redis_client.get(key)
    if not existing:
        return []
    redis_client.delete(key)
    return json.loads(existing)
