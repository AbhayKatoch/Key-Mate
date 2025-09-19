from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from twilio.twiml.messaging_response import MessagingResponse
from urllib.parse import parse_qs
from .views_twilio import EDIT_FIELDS_MAP

from .models import Broker, Property
from inventory.services.redis_setup import get_session, set_session, clear_session
from inventory.services.ai_intent import classify_intent
from .models import Broker, Property
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
            resp = handle_edit_broker_session(broker, msg, resp, session)
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

@csrf_exempt
def whatsapp_webhook_meta(request):
    """
    This replicates the broker Twilio webhook but for Meta Cloud API.
    """
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge)
        return HttpResponse(status=403)
    
    if request.method != "POST":
        return HttpResponse("Invalid", status=400)

    payload = json.loads(request.body.decode("utf-8"))
    entry = payload.get("entry", [])[0]
    changes = entry.get("changes", [])[0]
    value = changes.get("value", {})
    messages = value.get("messages", [])
    if not messages:
        return HttpResponse(status=200)

    msg_obj = messages[0]
    from_number = msg_obj.get("from")                      # client/broker phone
    text_body = msg_obj.get("text", {}).get("body", "").strip()

    phone_number_id = value.get("metadata", {}).get("phone_number_id")
    display_number = value.get("metadata", {}).get("display_phone_number")

    # ✅ Onboarding flow (broker using this WABA)
    broker = Broker.objects.filter(phone_number=display_number).first()
    if not broker:
        # If broker not found by WABA number → check onboarding
        broker = Broker.objects.filter(phone_number=from_number).first()

    if not broker:
        # Onboarding new broker
        # Here we simulate resp.message with a send_whatsapp_text
        # handle_onboarding still returns a Twilio MessagingResponse, so we extract text(s)
        from twilio.twiml.messaging_response import MessagingResponse
        resp = MessagingResponse()
        resp = handle_onboarding(from_number, text_body, resp)
        for m in get_texts_from_resp(resp):
            send_whatsapp_text(from_number, m)
        return HttpResponse(status=200)

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
                send_whatsapp_text(from_number, "⚠️ Edit session ended. Please restart with 'edit <property_id>'.")
                return HttpResponse(status=200)

            try:
                prop = Property.objects.get(broker=broker, property_id=property_id)
            except Property.DoesNotExist:
                clear_session(broker.id)
                send_whatsapp_text(from_number, "⚠️ Property not found. Edit session cleared.")
                return HttpResponse(status=200)

            if step == "choose_field":
                if text_body not in EDIT_FIELDS_MAP:
                    send_whatsapp_text(from_number, "⚠️ Invalid choice. Reply with 1-5.")
                    return HttpResponse(status=200)
                field = EDIT_FIELDS_MAP[text_body]
                session["step"] = "awaiting_value"
                session["field"] = field
                set_session(broker.id, session)
                send_whatsapp_text(from_number, f"✏️ Send me the new {field}.")
                return HttpResponse(status=200)

            elif step == "awaiting_value":
                field = session.get("field")
                new_value = text_body.strip()
                if field in ["price", "bhk"]:
                    try:
                        new_value = int(new_value)
                    except ValueError:
                        send_whatsapp_text(from_number, "⚠️ Please enter a valid number.")
                        return HttpResponse(status=200)
                elif field == "status":
                    if new_value not in ["active", "disabled", "disable"]:
                        send_whatsapp_text(from_number, "⚠️ Invalid status. Use 'active' or 'disable'.")
                        return HttpResponse(status=200)
                    if new_value == "disable":
                        new_value = "disabled"
                setattr(prop, field, new_value)
                prop.save()
                clear_session(broker.id)
                send_whatsapp_text(from_number, f"✅ Updated {field} for {prop.property_id} | {prop.title} to {new_value}.")
                return HttpResponse(status=200)

        # 🔹 New property media upload flow
        elif mode == "new_property":
            if text_body.lower() in ["done", "skip"]:
                from twilio.twiml.messaging_response import MessagingResponse
                resp = MessagingResponse()
                resp = handle_done(broker, resp)
                # for m in resp.messages:
                #     send_whatsapp_text(from_number, m.body)
                for m in get_texts_from_resp(resp):
                    send_whatsapp_text(from_number, m)
                return HttpResponse(status=200)

            num_media = len(msg_obj.get("image", {}))  # adapt for media
            if num_media > 0:
                from twilio.twiml.messaging_response import MessagingResponse
                resp = MessagingResponse()
                resp = handle_media(broker, msg_obj, resp)
                # for m in resp.messages:
                #     send_whatsapp_text(from_number, m.body)
                for m in get_texts_from_resp(resp):
                    send_whatsapp_text(from_number, m)
                return HttpResponse(status=200)

        # 🔹 Edit broker profile flow
        elif mode == "edit_broker":
            from twilio.twiml.messaging_response import MessagingResponse
            resp = MessagingResponse()
            resp = handle_edit_broker_session(broker, text_body, resp, session)
            # for m in resp.messages:
            #     send_whatsapp_text(from_number, m.body)
            for m in get_texts_from_resp(resp):
                send_whatsapp_text(from_number, m)
            return HttpResponse(status=200)

    # ✅ No session → use AI intent classification
    try:
        intent = classify_intent(text_body)
    except Exception:
        send_whatsapp_text(from_number, "⚠️ Sorry, I couldn’t understand. Type 'help' for commands.")
        return HttpResponse(status=200)

    action = intent.action
    if action in COMMANDS:
        from twilio.twiml.messaging_response import MessagingResponse
        resp = MessagingResponse()
        resp = COMMANDS[action](broker, intent, resp, msg=text_body)
        # for m in resp.messages:
        #     if m.body:
        #         send_whatsapp_text(from_number, m.body)
        for m in get_texts_from_resp(resp):
            if m:
                send_whatsapp_text(from_number, m)
            # if your handlers attach media you can also loop m.media and send_whatsapp_media
    else:
        send_whatsapp_text(from_number, "⚠️ Sorry, I didn’t understand. Type 'help' for guidance.")

    return HttpResponse(status=200)
    """
    Receives messages from Meta Cloud API (WhatsApp Business)
    """
    if request.method != "POST":
        return HttpResponse("Invalid", status=400)

    payload = json.loads(request.body.decode("utf-8"))
    entry = payload.get("entry", [])[0]
    changes = entry.get("changes", [])[0]
    value = changes.get("value", {})
    messages = value.get("messages", [])

    if not messages:
        return HttpResponse(status=200)

    msg_obj = messages[0]
    from_number = msg_obj.get("from")  # client phone
    text_body = msg_obj.get("text", {}).get("body", "")
    phone_number_id = value.get("metadata", {}).get("phone_number_id")
    display_number = value.get("metadata", {}).get("display_phone_number")

    # Find broker by Meta WABA number
    broker = Broker.objects.filter(phone_number=display_number).first()

    # KD-BROKER link flow
    if text_body.startswith("KD-BROKER-"):
        broker = Broker.objects.filter(broker_code__iexact=text_body.strip()).first()
        if broker:
            Session.objects.update_or_create(
                client_phone=from_number,
                defaults={"broker": broker}
            )
            send_whatsapp_text(from_number, f"Hey, I am {broker.name}'s assistant! Ask me about properties anytime.")
        else:
            send_whatsapp_text(from_number, "⚠️ Broker not found.")
        return HttpResponse(status=200)

    # Existing session
    session = Session.objects.filter(client_phone=from_number).first()
    if session:
        broker = session.broker

    if not broker:
        send_whatsapp_text(from_number, "⚠️ Broker not found. Please click your broker’s link to start.")
        return HttpResponse(status=200)

    # Classify intent
    intent = classify_intent(text_body)

    # Use your same handlers
    if intent.action == "list_properties":
        resp = handle_list(broker, intent, msg=text_body, resp=None)  # adapt if needed
        send_whatsapp_text(from_number, resp)  # your resp should return text
    elif intent.action == "view_property":
        resp = handle_view(broker, intent, msg=text_body, resp=None)
        send_whatsapp_text(from_number, resp)
        # for media → send_whatsapp_media(...)
    else:
        send_whatsapp_text(from_number, "⚠️ Sorry, I didn’t understand. You can say 'show flats in Mumbai' or 'view 10'.")

    return HttpResponse(status=200)