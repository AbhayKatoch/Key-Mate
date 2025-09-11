from twilio.rest import Client
import os

_twilio_client =  None

def get_client():
    global _twilio_client

    if _twilio_client is None:
        sid = os.getenv("TWILIO_SID")
        token = os.getenv("TWILIO_AUTH_TOKEN")
        
        _twilio_client = Client(sid, token)
    return _twilio_client

def send_whatsapp(to_number: str, body :str, from_number:str | None = None):
    client = get_client()
    from_env = from_number or os.getenv("TWILIO_WHATSAPP")

    if not from_env:
        raise RuntimeError("FROM NOT CONFIGURED")
    
    if not from_env.startswith("whatsapp:"):
        from_field = f"whatsapp:{from_env}"
    else:
        from_field = from_env

    to_field = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}"
    return client.messages.create(from_=from_field, to = to_field, body=body)