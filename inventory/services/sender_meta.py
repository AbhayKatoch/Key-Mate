# services/sender_meta.py
import os, requests

META_TOKEN = os.getenv("META_TOKEN")  # from Facebook developer app
PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")  # your WABA ID

def send_whatsapp_text(to, text):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": text}
    }
    requests.post(url, headers=headers, json=data)

def send_whatsapp_media(to, media_url, media_type="image"):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        media_type: {"link": media_url}
    }
    requests.post(url, headers=headers, json=data)
