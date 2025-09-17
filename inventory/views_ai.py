from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from twilio.twiml.messaging_response import MessagingResponse
from urllib.parse import parse_qs

from .models import Broker, Property
from inventory.services.redis_setup import get_session, set_session, clear_session
from inventory.services.ai_intent import classify_intent
from .models import Broker, Property
from .views_twilio import (
    handle_onboarding, handle_list, handle_view, handle_share,
    handle_edit, handle_delete, handle_activate, handle_disable, handle_share_all_to_client,
    handle_profile, handle_editprofile, handle_help, handle_new_property, handle_edit_broker_session, handle_done, handle_desc, handle_media, handle_bot_url
)

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
            from .views_twilio import EDIT_FIELDS_MAP
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
