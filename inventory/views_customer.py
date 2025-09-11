from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from twilio.twiml.messaging_response import MessagingResponse
from urllib.parse import parse_qs
import re
from .models import Property, Broker, MediaAsset
from .services.redis_setup import get_session, set_session, clear_session
from .services.ai_intent import classify_customer_intent
from .services.sharing_msg import generate_property_message

def handle_list_properties(intent, resp):
    page = intent.filters.get("page", 1) or 1
    city = intent.filters.get("city")
    bhk = intent.get("bhk")
    price_filter = intent.get("price")
    qs = Property.objects.filter(status="active").order_by("-created_at")

    if city:
        qs = qs.filter(city__iexact=city)

    if bhk:
        try:
            bhk_int = int(bhk)
            qs = qs.filter(bhk=bhk_int)
        except ValueError:
            pass

    
    if price_filter:
        match = re.match(r"(<=|>=|<|>|=)?\s*([\d,.]+)", str(price_filter))
        if match:
            op, val = match.groups()
            val = float(val.replace(",", ""))

            if op in ("<", "<="):
                max_val = val * 1.15
                qs = qs.filter(price__lte=max_val)
            elif op in (">", ">="):
                qs = qs.filter(price__gte=val)
            else:
                max_val = val * 1.15
                qs = qs.filter(price__lte=max_val)

    if not qs.exists():
        resp.message("No Properties Found.")
        return resp
    
    page_size = 10
    start = (page - 1) * page_size
    end = start + page_size
    properties = qs[start:end]
    
    lines = []

    for p in properties:
        bhk_display = f"{p.bhk} BHK" if p.bhk else ""
        if p.bhk == 1 and (
            "studio" in (p.title or "").lower() 
            or "studio" in (p.description_raw or "").lower()
        ):
            bhk_display = "1 RK"

        lines.append(
            f"[{p.property_id}] {p.title or ''} | {bhk_display} | "
            f"{p.city or ''} | {p.price or 'N/A'} {p.currency or ''}"
        )

    total_pages = (qs.count() + page_size - 1) // page_size

    reply_text = (
        f"📋 Available Properties (Page {page}/{total_pages}):\n\n" +
        "\n".join(lines)
    )
    if page < total_pages:
        reply_text += f"\n\n👉 Reply 'list {page+1}' for next page"

    resp.message(reply_text)
    return resp

def handle_view_property(intent, resp):
    property_id = intent.property_id
    if not property_id:
        resp.message("⚠️ Please provide a property ID. Example: view 123")
        return resp
    
    try:
        prop = Property.objects.get(property_id=property_id, status="active")
    except Property.DoesNotExist:
        resp.message("Property Not Found")
        return resp
    
    broker = prop.broker
    stylish_msg = generate_property_message(prop, broker)
    resp.message(stylish_msg)
    


    media_assets = MediaAsset.objects.filter(property=prop)
    if media_assets.exists():
        for media in media_assets:
            if media.media_type == "image":
                msg_with_media = resp.message("📸 Property Image")
                msg_with_media.media(media.storage_url)
            elif media.media_type == "video":
                msg_with_media = resp.message("🎥 Property Video")
                msg_with_media.media(media.storage_url)

    return resp

def handle_help(resp):
    resp.message(
        "*KeyMate Customer Help*\n\n"
        "Commands:\n\n"
        "🏡 Property Browsing:\n"
        "- list (or list <city>) → View available properties\n"
        "- view <property_id> → View property details (paraphrased message)\n\n"
        "❓ Help:\n"
        "- help → For your help guide"
    )
    return resp


@csrf_exempt
def customer_webhook(request):
    if request.method == "POST":
        body = request.body.decode("utf-8")
        data = parse_qs(body)
        msg = data.get("Body", [""])[0]
        from_number = data.get("From", [""])[0].replace("whatsapp:", "")

        resp = MessagingResponse()

        intent = classify_customer_intent(msg)

        COMMANDS = {
            "list_properties": handle_list_properties,
            "view_property": handle_view_property,
        }

        if intent.action in COMMANDS:
            handler = COMMANDS[intent.action]
            resp = handler(from_number, intent, resp, msg)
        else:
            resp.message("⚠️ Sorry, I didn’t understand. You can say 'show flats in Mumbai' or 'view 10'.")

        return HttpResponse(str(resp), content_type="application/xml")

    return HttpResponse("Invalid request", status=400)