from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from twilio.twiml.messaging_response import MessagingResponse
from urllib.parse import parse_qs

from .models import Broker
from inventory.services.redis_setup import get_session, set_session, clear_session
from inventory.services.ai_intent import classify_intent
from .views_twilio import (
    handle_onboarding, handle_list, handle_view, handle_share,
    handle_edit, handle_delete, handle_activate, handle_disable,
    handle_profile, handle_editprofile, handle_help
)

COMMANDS = {
    "list_properties": handle_list,
    "view_property": handle_view,
    "share_property": handle_share,
    "edit_property": handle_edit,
    "delete_property": handle_delete,
    "activate_property": handle_activate,
    "disable_property": handle_disable,
    "profile": handle_profile,
    "editprofile": handle_editprofile,
    "help": handle_help,
}

@csrf_exempt
def whatsapp_webhook(request):
    if request.method != "POST":
        return HttpResponse("Invalid request", status=400)

    body = request.body.decode("utf-8")
    data = parse_qs(body)
    msg = data.get("Body", [""])[0]
    from_number = data.get("From", [""])[0]
    phone = from_number.replace("whatsapp:", "")
    resp = MessagingResponse()

    # Check if broker exists
    try:
        broker = Broker.objects.get(phone_number=phone)
    except Broker.DoesNotExist:
        return HttpResponse(str(handle_onboarding(phone, msg, resp)), content_type="application/xml")

    # Use AI intent classifier
    try:
        intent = classify_intent(msg)
    except Exception as e:
        resp.message(f"⚠️ Sorry, I couldn’t understand. Type 'help' for commands.")
        return HttpResponse(str(resp), content_type="application/xml")

    action = intent.action

    if action in COMMANDS:
        handler = COMMANDS[action]
        resp = handler(broker, msg, resp)
    else:
        resp.message("⚠️ Sorry, I didn’t understand. Type 'help' for guidance.")

    return HttpResponse(str(resp), content_type="application/xml")