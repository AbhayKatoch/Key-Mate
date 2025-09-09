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
    handle_profile, handle_editprofile, handle_help, handle_new_property
)

COMMANDS = {
    "new_property": handle_new_property,
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
def whatsaap_webhook(request):
    body = request.body.decode("utf-8")

    data = parse_qs(body)
    msg = request.POST.get("Body", "").strip()

    from_number = data.get("From",[""])[0]

    phone = from_number.replace("whatsapp:", "")

    try:
        broker = Broker.objects.get(phone_number=phone)
    except Broker.DoesNotExist:
        resp = handle_onboarding(phone, msg, resp)
        return HttpResponse(str(resp), content_type="application/xml")

    resp = MessagingResponse()

        # ✅ Step 1: classify
    intent = classify_intent(msg)

    # ✅ Step 2: route based on action
    action_map = {
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

    action = intent.action
    if action in COMMANDS:
        handler = COMMANDS[action]
        resp = handler(broker, intent, resp)  # pass intent now
    else:
        resp.message("⚠️ Sorry, I didn’t understand. Type 'help' for guidance.")
    return HttpResponse(str(resp), content_type="application/xml")
