from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from twilio.twiml.messaging_response import MessagingResponse
from urllib.parse import parse_qs
from .views_twilio import EDIT_FIELDS_MAP

from .models import Broker, Property
from inventory.services.redis_setup import get_session, set_session, clear_session, is_media_processed, mark_media_processed, add_media_to_queue, pop_media_queue
from inventory.services.ai_intent import classify_intent
from .models import Broker, Property, MediaAsset
from .views_twilio import (
    handle_onboarding, handle_list, handle_view, handle_share,
    handle_edit, handle_delete, handle_activate, handle_disable, handle_share_all_to_client,
    handle_profile, handle_editprofile, handle_help, handle_new_property, handle_edit_broker_session, handle_done, handle_desc, handle_media, handle_bot_url
)
from .services.sender_meta import send_whatsapp_text, send_whatsapp_media
import json

COMMANDS = {
    "new_property": handle_new_property,
    "list_properties": handle_list,
    "view_property": handle_view,
    "share_property": handle_share,
    "share_all_to_client": handle_share_all_to_client,
    "edit_property": handle_edit,
    "delete_property": handle_delete,
    "activate_property": handle_activate,
    "disable_property": handle_disable,
    "profile": handle_profile,
    "editprofile": handle_editprofile,
    "help": handle_help,
    "boturl": handle_bot_url
}

@csrf_exempt
def whatsaap_webhook(request):
    if request.method != "POST":
        return HttpResponse("Invalid request", status=400)

    body = request.body.decode("utf-8")
    data = parse_qs(body)
    msg = data.get("Body", [""])[0].strip()
    from_number = data.get("From", [""])[0]
    phone = from_number.replace("whatsapp:", "")
    resp = MessagingResponse()

    # ✅ Onboarding flow
    try:
        broker = Broker.objects.get(phone_number=phone)
    except Broker.DoesNotExist:
        resp = handle_onboarding(phone, msg, resp)
        return HttpResponse(str(resp), content_type="application/xml")

    # ✅ Check session first
    session = get_session(broker.id)
    if session:
        mode = session.get("mode")

        # 🔹 Edit property flow
        if mode == "edit":
            property_id = session.get("property_id")
            step = session.get("step")

            if not property_id:
                clear_session(broker.id)
                resp.message("⚠️ Edit session ended. Please restart with 'edit <property_id>'.")
                return HttpResponse(str(resp), content_type="application/xml")

            try:
                prop = Property.objects.get(broker=broker, property_id=property_id)
            except Property.DoesNotExist:
                clear_session(broker.id)
                resp.message("⚠️ Property not found. Edit session cleared.")
                return HttpResponse(str(resp), content_type="application/xml")

            # Step 1: choose field
            if step == "choose_field":
                if msg not in EDIT_FIELDS_MAP:
                    resp.message("⚠️ Invalid choice. Reply with 1-5.")
                    return HttpResponse(str(resp), content_type="application/xml")

                field = EDIT_FIELDS_MAP[msg]
                session["step"] = "awaiting_value"
                session["field"] = field
                set_session(broker.id, session)

                resp.message(f"✏️ Send me the new {field}.")
                return HttpResponse(str(resp), content_type="application/xml")

            # Step 2: awaiting value
            elif step == "awaiting_value":
                field = session.get("field")
                new_value = msg.strip()

                if field in ["price", "bhk"]:
                    try:
                        new_value = int(new_value)
                    except ValueError:
                        resp.message("⚠️ Please enter a valid number.")
                        return HttpResponse(str(resp), content_type="application/xml")

                elif field == "status":
                    if new_value not in ["active", "disabled", "disable"]:
                        resp.message("⚠️ Invalid status. Use 'active' or 'disable'.")
                        return HttpResponse(str(resp), content_type="application/xml")
                    if new_value == "disable":
                        new_value = "disabled"

                setattr(prop, field, new_value)
                prop.save()

                clear_session(broker.id)
                resp.message(f"✅ Updated {field} for {prop.property_id} | {prop.title} to {new_value}.")
                return HttpResponse(str(resp), content_type="application/xml")

        # 🔹 New property media upload flow
        elif mode == "new_property":
            if msg.lower() in ["done", "skip"]:
                resp = handle_done(broker, resp)
                return HttpResponse(str(resp), content_type="application/xml")

            num_media = int(data.get("NumMedia", [0])[0] or 0)
            if num_media > 0:
                resp = handle_media(broker, data, resp)
                return HttpResponse(str(resp), content_type="application/xml")

        # 🔹 Edit broker profile flow
        elif mode == "edit_broker":
            resp = handle_edit_broker_session(broker, msg, session)
            return HttpResponse(str(resp), content_type="application/xml")

    # ✅ No session → use AI intent classification
    try:
        intent = classify_intent(msg)
    except Exception:
        resp.message("⚠️ Sorry, I couldn’t understand. Type 'help' for commands.")
        return HttpResponse(str(resp), content_type="application/xml")

    action = intent.action
    if action in COMMANDS:
        handler = COMMANDS[action]
        resp = handler(broker, intent, resp, msg=msg)  # unified signature
    else:
        resp.message("⚠️ Sorry, I didn’t understand. Type 'help' for guidance.")

    return HttpResponse(str(resp), content_type="application/xml")


import os
VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")
from xml.etree import ElementTree

def get_texts_from_resp(resp):
    """
    Extracts all <Body> messages from a Twilio MessagingResponse.
    Useful when reusing Twilio handlers for Meta.
    """
    texts = []
    try:
        root = ElementTree.fromstring(str(resp))
        for msg in root.findall("Message"):
            body = msg.find("Body")
            if body is not None and body.text:
                texts.append(body.text)
    except Exception:
        pass
    return texts


def make_response():
    return {"texts": [], "medias": []}



from inventory.services.redis_setup import get_session, set_session

def is_duplicate_message(msg_id: str) -> bool:
    """
    Check if a WhatsApp message ID was already processed.
    Uses Redis to mark processed IDs.
    """
    if not msg_id:
        return False

    key = f"msg_processed:{msg_id}"
    if get_session(key):
        return True  # already handled
    # store with short TTL (e.g. 1 day)
    set_session(key, True, ttl=3600)
    return False




import requests, cloudinary.uploader,os

META_TOKEN = os.getenv("META_TOKEN")

def handle_meta_media_upload(broker, property_obj, media_id, from_number):
    try:
        if is_media_processed(media_id):
            return None
        
        url = f"https://graph.facebook.com/v22.0/{media_id}"
        headers = {"Authorization": f"Bearer {META_TOKEN}"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        direct_url = response.json().get("url")

        media_response = requests.get(direct_url, headers=headers, stream=True, timeout=20)
        media_response.raise_for_status()

        upload_result = cloudinary.uploader.upload(
            media_response.raw,
            resource_type = "auto",
            folder="property_media"
        ) 

        file_url = upload_result["secure_url"]
        file_type = upload_result["resource_type"]

        MediaAsset.objects.create(
            property=property_obj,
            media_type=file_type,
            storage_url=file_url
        )

        mark_media_processed(media_id)
        # send_whatsapp_text(from_number, "✅ Media uploaded successfully!")
        return file_url
    
    except Exception as e:
        print(f"[ERROR] Failed to upload media {media_id}: {e}")
        send_whatsapp_text(from_number, "⚠️ Media upload failed, please try again.")
        return None


from threading import Timer

upload_timers = {}  # global dict to avoid multiple timers per broker

def schedule_media_upload(broker, property_obj, phone):
    """Triggered a few seconds after the last image arrives."""
    broker_id = broker.id
    media_batch = pop_media_queue(broker_id)
    if not media_batch:
        return

    send_whatsapp_text(phone, f"📸 Got {len(media_batch)} image(s)! Uploading them now...")

    success = 0
    for media in media_batch:
        media_id = media["id"]
        result = handle_meta_media_upload(broker, property_obj, media_id, phone)
        if result:
            success += 1
    send_whatsapp_text(
        phone,
        f"✅ Uploaded {success}/{len(media_batch)} image(s) successfully!\n\n"
        "If you have more, send them now.\n"
        "When you're done, type *done* or *skip* to finish adding this property."
    )
    upload_timers.pop(broker_id, None)
    Timer(25.0, lambda: send_whatsapp_text(
        phone,
        "💡 Looks like you’re done sending images!\n"
        "Type *done* to finalize this property, or *skip* to cancel."
    )).start()







import logging
@csrf_exempt
def whatsapp_webhook_meta(request):
    logging.info(f"Webhook called: {request.method} {request.path}")
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge)
        return HttpResponse(status=403)
    if request.method != "POST":
        return HttpResponse("Invalid request", status=400)
    
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponse("Invalid JSON", status=400)
    
    entry = body.get("entry", [])[0]
    changes = entry.get("changes", [])[0]
    value = changes.get("value",{})
    messages = value.get("messages",[])

    if not messages:
        return HttpResponse("No messages", status=200)
    
    msg_obj = messages[0]
    msg_id = msg_obj.get("id")
    msg = msg_obj.get("text", {}).get("body","").strip()
    phone = msg_obj.get("from")
    if phone.startswith("whatsapp:"):
        phone = phone.replace("whatsapp:", "").strip()
    if phone.startswith("+91"):
        phone = phone[3:]
    elif phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]
    phone = phone.strip()[-10:]

    if msg_id and is_duplicate_message(msg_id):
        logging.info(f"Duplicate message {msg_id} from {phone}, ignoring.")
        return HttpResponse("Duplicate message", status=200)

    try:
        broker = Broker.objects.get(phone_number=phone)
    except Broker.DoesNotExist:
        handle_onboarding(phone, msg)
        return HttpResponse("Onboarding sent", status=200)
    
    session = get_session(broker.id)
    if session:
        mode = session.get("mode")

        if mode == "edit":
            property_id = session.get("property_id")
            step = session.get("step")

            if not property_id:
                clear_session(broker.id)
                send_whatsapp_text(phone, "⚠️ Edit session ended. Please restart with 'edit <property_id>'.")
                return HttpResponse("Session cleared", status=200)

            try:
                prop = Property.objects.get(broker=broker, property_id=property_id)
            except Property.DoesNotExist:
                clear_session(broker.id)
                send_whatsapp_text(phone, "⚠️ Property not found. Edit session cleared.")
                return HttpResponse("Property not found", status=200)

            if step == "choose_field":
                if msg not in EDIT_FIELDS_MAP:
                    send_whatsapp_text(phone, "⚠️ Invalid choice. Reply with 1-5.")
                    return HttpResponse("Invalid choice", status=200)

                field = EDIT_FIELDS_MAP[msg]
                session["step"] = "awaiting_value"
                session["field"] = field
                set_session(broker.id, session)

                send_whatsapp_text(phone, f"✏️ Send me the new {field}.")
                return HttpResponse("Awaiting value", status=200)

            elif step == "awaiting_value":
                field = session.get("field")
                new_value = msg.strip()

                if field in ["price", "bhk"]:
                    try:
                        new_value = int(new_value)
                    except ValueError:
                        send_whatsapp_text(phone, "⚠️ Please enter a valid number.")
                        return HttpResponse("Invalid number", status=200)

                elif field == "status":
                    if new_value.lower() not in ["active", "disabled", "disable"]:
                        send_whatsapp_text(phone, "⚠️ Invalid status. Use 'active' or 'disable'.")
                        return HttpResponse("Invalid status", status=200)
                    if new_value.lower() == "disable":
                        new_value = "disabled"
                    if new_value.lower() == "active":
                        new_value = "active"

                setattr(prop, field, new_value)
                prop.save()

                clear_session(broker.id)
                send_whatsapp_text(phone, f"✅ Updated {field} for {prop.property_id} | {prop.title} to {new_value}.")
                return HttpResponse("Property updated", status=200)
        elif mode == "new_property":
            if msg.lower() in ["done", "skip"]:
                resp= handle_done(broker)
                for txt in resp.get("texts", []):
                    send_whatsapp_text(phone, txt)
                send_whatsapp_text(phone, "🎯 All set! Your property is live now. You can view it in your dashboard or type 'list' to see all properties.")

                return HttpResponse("Done handled", status=200)

            # num_media = len(msg_obj.get("image", [])) + len(msg_obj.get("video", []))
            # if num_media > 0:
            #     resp = handle_media(broker, msg_obj)
            #     for txt in resp.get("texts", []):
            #         send_whatsapp_text(phone, txt)
            #     for media in resp.get("medias", []):
            #         send_whatsapp_media(phone, media["url"], media["type"])
            #     return HttpResponse("Media handled", status=200)
            if "image" in msg_obj or "video" in msg_obj:
                try:
                    property_id = session.get("property_id")
                    property_obj = Property.objects.get(broker=broker, property_id=property_id)
                except Property.DoesNotExist:
                    clear_session(broker.id)
                    send_whatsapp_text(phone, "⚠️ Property not found. Please start again.")
                    return HttpResponse("Property not found", status=200)

                media_types = ["image", "video"]
                for m_type in media_types:
                    media_obj = msg_obj.get(m_type)
                    if not media_obj:
                        continue

                    # WhatsApp always sends single media per webhook
                    if isinstance(media_obj, dict) and "id" in media_obj:
                        add_media_to_queue(broker.id, media_obj["id"])

                # debounce uploads: wait 3 seconds before processing batch
                if broker.id in upload_timers:
                    upload_timers[broker.id].cancel()

                upload_timers[broker.id] = Timer(3.0, schedule_media_upload, args=(broker, property_obj, phone))
                upload_timers[broker.id].start()

                return HttpResponse("Media queued", status=200)
        elif mode == "edit_broker":
            resp = handle_edit_broker_session(broker, msg, session)
            for txt in resp.get("texts", []):
                send_whatsapp_text(phone, txt)
            for media in resp.get("medias", []):
                send_whatsapp_media(phone, media["url"], media["type"])
            return HttpResponse("Edit broker session handled", status=200)
            # ✅ Handle Password Reset via WhatsApp
        elif mode == "reset_password":
            step = session.get("step")
            broker_id = session.get("broker_id")

            if step == "awaiting_password":
                new_password = msg.strip()
                try:
                    broker = Broker.objects.get(id=broker_id)
                    broker.set_password(new_password)
                    broker.save()
                    clear_session(broker.id)
                    send_whatsapp_text(phone, "✅ Your password has been reset successfully!\nYou can now log in to your account.")
                    return HttpResponse("Password reset successful", status=200)
                except Broker.DoesNotExist:
                    clear_session(broker.id)
                    send_whatsapp_text(phone, "⚠️ Something went wrong. Please try again later.")
                    return HttpResponse("Broker not found", status=400)

    try:
        # ⛔ Skip intent classification for pure media messages
# ✅ Skip intent classification only if message has media but no text
        if ("image" in msg_obj or "video" in msg_obj) and not msg.strip():
            return HttpResponse("Media upload handled", status=200)

        intent = classify_intent(msg)
    except Exception:
        send_whatsapp_text(phone, "⚠️ Sorry, I couldn’t understand. Type 'help' for commands.")
        return HttpResponse(status =200)

    action = intent.action
    if action in COMMANDS:
        handler = COMMANDS[action]
        resp = handler(broker, intent, msg=msg)
        for txt in resp.get("texts", []):
            send_whatsapp_text(phone, txt)
        for media in resp.get("medias", []):
            send_whatsapp_media(phone, media["url"], media["type"])
    else:
        send_whatsapp_text(phone, "⚠️ Sorry, I didn’t understand. Type 'help' for guidance.")

    return HttpResponse(status=200)
