from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from twilio.twiml.messaging_response import MessagingResponse
from inventory.services.extract import extract
from .models import Broker, Property, MediaAsset
from urllib.parse import parse_qs
from inventory.services.redis_setup import set_session, get_session, clear_session
from dotenv import load_dotenv
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import os
import requests
import cloudinary.uploader

load_dotenv()
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

def handle_activate(broker, msg, resp):
    property_number = msg.split()[-1]
    try:
        prop = Property.objects.get(broker = broker, property_id=property_number)
        prop.status = "active"
        prop.save()
        resp.message(f"✅ {prop.property_id} | {prop.title} is now active")
    except Property.DoesNotExist:
        resp.message("❌ Property not found.")
    return  resp

def handle_disable(broker, msg, resp):
    property_number = msg.split()[-1]
    try: 
        prop = Property.objects.get(broker = broker, property_id=property_number)
        prop.status = "disabled"
        prop.save()
        resp.message(f"{prop.property_id} | ({prop.title}) has been Disabled.")
    except Property.DoesNotExist:
        resp.message("Property not found")
    return resp
                

def handle_delete(broker, msg, resp):
    property_number = msg.split()[-1]
    try: 
        prop = Property.objects.get(broker = broker, property_id=property_number)
        prop.delete()
        resp.message(f"Property {property_number} Deleted.")
    except Property.DoesNotExist:
        resp.message("Property not found")
    return resp
        

def handle_list(broker, msg, resp):
    parts = msg.split()
    page = int(parts[1]) if len(parts) > 1 else 1
    page_size = 10
    start = (page - 1) * page_size
    end = start + page_size
    properties = Property.objects.filter(broker = broker).order_by("-created_at")
    if not properties:
        resp.message("You don't have any properties yet.")
        return resp
    
    lines = []
    for p in properties[start:end]:
        lines.append(f"[{p.property_id}] | {p.title} | {p.city or ''} | {p.status}")

    total_pages = (properties.count() + page_size -1) // page_size

    reply_text = (
        f"📋 Your properties (Page {page}/{total_pages}):\n\n" +
                "\n".join(lines) 
        )
    if page < total_pages:
        reply_text += f"\n\n👉 Reply 'list {page+1}' for next page"
        
    resp.message(reply_text)
        
    return resp

def handle_yes(broker, msg, resp):
    session = get_session(broker.id)
    if not session or "pending_property" not in session:
        resp.message("No Property pending confirmation")
    
    prop = session["pending_property"]
    clear_session(broker.id)
    resp.message(f"Saved property draft: {prop['title']} ({prop['city']})")
    return resp

def handle_no(broker, msg, resp):
    clear_session(broker.id)
    resp.message("Property Discarded")
    return resp


EDIT_FIELDS_MAP = {
    "1": "price",
    "2": "city",
    "3": "bhk",
    "4": "furnishing",
    "5": "description_raw",
}

def handle_edit(broker, msg, resp):
    parts = msg.split()
    if len(parts) < 2:
        resp.message("Please provide a property ID. Example: edit 123")
        return resp

    property_number = parts[1]
    try:
        prop = Property.objects.get(broker=broker, property_id=property_number)
    except Property.DoesNotExist:
        resp.message("❌ Property not found.")
        return resp

    session = {
        "mode": "edit",
        "property_id": prop.property_id,
        "step": "choose_field",
    }
    set_session(broker.id, session)

    resp.message(
        f"Editing [{prop.property_id}] {prop.title or 'Property'}\n"
        f"What do you want to edit?\n\n"
        f"1️⃣ Price\n"
        f"2️⃣ City\n"
        f"3️⃣ BHK\n"
        f"4️⃣ Furnishing\n"
        f"5️⃣ Description\n\n"
        f"👉 Reply with the number"
    )
    return resp


def handle_desc(broker, msg, resp):
    session = {
        "mode": "new_property",
        "step": "awaiting_media",
        "description": msg,
        "media": []

    }
    set_session(broker.id, session)
    resp.message("Got it! Now upload images/videos.\n👉 Type 'done' when finished, or 'skip' if no image is there.")
    return resp



def fetch_and_store_media(media_url, broker_id, index, ext="jpg"):
    auth = (TWILIO_SID, TWILIO_AUTH_TOKEN)
    response = requests.get(media_url, auth = auth)
    response.raise_for_status()
    if ext in ["jpg", "jpeg", "png"]:
        resource_type = "image"
    elif ext in ["mp4", "mov"]:
        resource_type = "video"
    else:
        resource_type = "raw"
    upload_result = cloudinary.uploader.upload(
        response.content,
        resource_type=resource_type,
        folder="property_media",  # optional folder in your Cloudinary
        public_id=f"{broker_id}_{index}",
        overwrite=True
    )

    return upload_result["secure_url"]

    

def handle_media(broker, data, resp):
    session = get_session(broker.id)
    if not session or session.get("mode") != "new_property":
        resp.message("⚠️ No active property creation in progress.")
        return resp

    num_media = int(data.get("NumMedia", [0])[0] or 0)
    for i in range(num_media):
        media_url = data.get(f"MediaUrl{i}", [None])[0]
        content_type = data.get(f"MediaContentType{i}", [""])[0]
        if not media_url:
            continue
        if "image" in content_type:
            media_type, ext = "image", "jpg"
        elif "video" in content_type:
            media_type, ext = "video", "mp4"
        else:
            media_type, ext = "other", "bin"

        public_url = fetch_and_store_media(media_url, broker.id, i, ext)
        session["media"].append({"url": public_url, "type": media_type, "order": i})

    set_session(broker.id, session)
    resp.message(f"📥 Added {num_media} file(s). Upload more or type 'done' when finished.")
    return resp

def handle_done(broker, resp):
    session = get_session(broker.id)
    if not session or session.get("mode") != "new_property":
        resp.message("⚠️ Nothing to finalize.")
        return resp

    description = session["description"]
    media = session["media"]

    prop = extract(broker, description=description, media_urls=[m["url"] for m in media])
    for m in media:
        MediaAsset.objects.create(property=prop, media_type=m["type"], storage_url=m["url"], order=m["order"])

    set_session(broker.id, {"mode": "confirm", "pending_property_id": prop.property_id})

    resp.message(
        f" New property added as Draft.\n\n"
        f"[{prop.property_id}] {prop.title} \n"
        f" {prop.bhk or ''} BHK in {prop.city or ''} for {prop.sale_or_rent}\n"
        f" {prop.area_sqft or 'N/A'} sqrt\n"
        f" {prop.furnishing or ''}\n"
        f" {prop.price or 'N/A'} {prop.currency}\n"
        f" near {prop.locality}\n"
        f" Status: {prop.status.title()}\n\n"
        f"👉 Reply 'Activate {prop.property_id}' to publish\n"
        f"👉 Reply 'Disable {prop.property_id}' to hide later"
    )
    return resp

def handle_view(broker, msg, resp):
    parts = msg.split()
    if len(parts) < 2:
        resp.message("⚠️ Please provide a property ID. Example: view 123")
        return resp

    property_number = parts[1]
    try:
        prop = Property.objects.get(broker=broker, property_id=property_number)
    except Property.DoesNotExist:
        resp.message("❌ Property not found.")
        return resp

    lines = [f"🏠 [{prop.property_id}] {prop.title or ''}"]
    if prop.price:
        lines.append(f"Price: {prop.price} {prop.currency or ''}")
    if prop.sale_or_rent:
        lines.append(f"Type: {prop.sale_or_rent.title()}")
    if prop.city:
        lines.append(f"City: {prop.city}")
    if prop.locality:
        lines.append(f"Locality: {prop.locality}")
    if prop.area_sqft:
        lines.append(f"Area: {prop.area_sqft} sqft")
    if prop.bhk:
        lines.append(f"BHK: {prop.bhk}")
    if prop.furnishing:
        lines.append(f"Furnishing: {prop.furnishing}")
    if prop.amenities:
        if isinstance(prop.amenities, list):
            lines.append("Amenities: " + " | ".join(prop.amenities))
        elif isinstance(prop.amenities, str):
            lines.append("Amenities: " + prop.amenities)
    if prop.maintenance:
        lines.append(f"Maintenance: {prop.maintenance}")
    if prop.deposit:
        lines.append(f"Deposit: {prop.deposit}")
    if prop.source_broker_name:
        lines.append(f"Source Name: {prop.source_broker_name}")
    if prop.source_broker_phone:
        lines.append(f"Source Phone Number: {prop.source_broker_phone}")
    if prop.status:
        lines.append(f"Status: {prop.status.title()}")

    details_msg = "\n".join(lines)
    resp.message(details_msg)

    media_assets = MediaAsset.objects.filter(property=prop)
    for media in media_assets:
        msg_with_media = resp.message("📸 Property Media")
        msg_with_media.media(media.storage_url)

    return resp


@csrf_exempt
def whatsaap_webhook(request):

    if request.method == "POST":
        body = request.body.decode("utf-8")
        data = parse_qs(body)

        msg = data.get("Body",[""])[0]
        from_number = data.get("From",[""])[0]

        phone = from_number.replace("whatsapp:", "")
        resp = MessagingResponse()

        try:
            broker = Broker.objects.get(phone_number=phone)
        except Broker.DoesNotExist:
            resp.message("Sorry, Your number is not registered as broker.")
            return HttpResponse(str(resp), content_type = "application/xml")


        session = get_session(broker.id)
        if session:
            if session.get("mode") == "edit":
                property_id = session.get("property_id")
                step = session.get("step")

                if not property_id:
                    clear_session(broker.id)
                    resp.message("Edit Session ended. Please Restart with 'edit <property number>'.")
                    return HttpResponse(str(resp), content_type="application/xml") 
                
                try:
                    prop = Property.objects.get(broker=broker, property_id=property_id)
                except Property.DoesNotExist:
                    clear_session(broker.id)
                    resp.message("⚠️ Property not found. Edit session cleared.")
                    return HttpResponse(str(resp), content_type="application/xml")

                if step == "choose_field":

                    if msg not in EDIT_FIELDS_MAP:
                        resp.message("⚠️ Invalid choice. Reply with 1-5.")
                        return HttpResponse(str(resp), content_type="application/xml")
                    
                    field = EDIT_FIELDS_MAP[msg]
                    session["step"] = "awaiting_value"
                    session["field"] = field
                    set_session(broker.id, session)
                    resp.message(f" Send me the new {field}")
                    return HttpResponse(str(resp), content_type="application/xml")
                
                elif step == "awaiting_value":
                    field = session.get("field")
                    new_value = msg

                    if field in ["price", "bhk"]:
                        try: 
                            new_value = int(new_value)
                        except ValueError:
                            resp.message("⚠️ Please enter a valid number.")
                            return HttpResponse(str(resp), content_type="application/xml")
                        
                    setattr(prop, field, new_value)
                    prop.save()

                    clear_session(broker.id)
                    resp.message(f"Updated {field} for {prop.property_id} | {prop.title} to {new_value}.")
                    return HttpResponse(str(resp), content_type="application/xml")
                
            elif session.get("mode") == "new_property":
                if msg.lower() in ["done", "skip"]:
                    resp = handle_done(broker, resp)
                    return HttpResponse(str(resp), content_type="application/xml")


                num_media = int(data.get("NumMedia", [0])[0] or 0)
                if num_media > 0:
                    resp = handle_media(broker, data, resp)
                    return HttpResponse(str(resp), content_type="application/xml")



        COMMANDS = {
            "activate": handle_activate,
            "disable": handle_disable,
            "delete": handle_delete,
            "list": handle_list,
            "yes": handle_yes,
            "no": handle_no,
            "edit": handle_edit,
            "view": handle_view
        }

        for cmd, handler in COMMANDS.items():
            if msg.lower().startswith(cmd):
                resp = handler(broker, msg, resp)
                return HttpResponse(str(resp), content_type="application/xml")


            

        resp = handle_desc(broker, msg, resp)

        return HttpResponse(str(resp), content_type = "application/xml")
    

    return HttpResponse("Invalid request", status=400)

