# services/sender_meta.py
import os, requests
from dotenv import load_dotenv
load_dotenv()

META_TOKEN = os.getenv("META_TOKEN")  # from Facebook developer app
PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")  # your WABA ID
import logging
def send_whatsapp_text(to, text):
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_TOKEN}",
        "Content-Type": "application/json"
    }
    if not to.startswith("+"):
        to = f"+91{to}"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        logging.info(f"Meta send text -> {to} | status {r.status_code} | resp {r.text}")
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.exception("Failed to send whatsapp text via Meta")
        return None

def send_whatsapp_media(to, media_url, media_type="image"):
    # ✅ Ensure valid URL and consistent API version
    url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_TOKEN}",
        "Content-Type": "application/json"
    }

    if not to.startswith("+"):
        to = f"+91{to}"

    # ✅ Correct Meta API payload
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": media_type,
        media_type: {
            "link": media_url
        }
    }

    try:
        logging.info(f"📤 Sending media to {to}: {payload}")
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        logging.info(f"Meta media response ({r.status_code}): {r.text}")
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logging.exception("❌ Failed to send whatsapp media via Meta")
        return None
