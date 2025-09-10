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
from .services.sharing_msg import generate_property_message

load_dotenv()
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

def handle_onboarding(phone, msg, resp):
    session = get_session(phone)

    if not session:
        set_session(phone, {"mode": "onboarding", "step": "ask_name"})
        resp.message("Welcome to KeyMate!\n Let's get you onboarded.\n\nPlease tell me your *full name*.")
        return resp
    
    step = session.get("step")

    if step == "ask_name":
        session["name"] = msg.strip()
        session["step"] = "ask_mail"
        set_session(phone, session)
        resp.message(f"Thanks {msg}! \nNow tell me your e-mail (or type 'skip' if none).")
        return resp
    
    elif step == "ask_mail":
        mail = None if msg.lower() == 'skip' else msg.strip()

        broker = Broker.objects.create(
            name = session["name"],
            phone_number = phone,
            email = mail
        )

        clear_session(phone)

        resp.message(
            f"✅ You’re registered, {broker.name}!\n\n"
            f"Here’s how to use KeyMate:\n"
            f"1️⃣ Send me a property description → I’ll extract details.\n"
            f"2️⃣ Upload images/videos → type 'done' when finished.\n"
            f"3️⃣ I’ll create a draft property for you.\n"
            f"4️⃣ Use commands:\n"
            f"   • 'list' → see all your properties\n"
            f"   • 'disable <id>' → hide the property from user\n"
            f"   • 'delete <id>' → delete the property\n"
            f"   • 'edit <id>' → edit property details\n"
            f"   • 'share <id>' → sharing message\n"
            f"   • 'profile' → view your broker profile\n"
            f"   • 'editprofile' → edit your broker profile\n"
            f"   • 'help' → guide incase you stuck somewhere\n"
        )
        return resp
    
    return resp

def handle_profile(broker, intent, resp, msg=None):
    lines = [f"👤 *Your Profile*",
             f"Name: {broker.name or 'N/A'}",
             f"Phone: {broker.phone_number}",
             f"Email: {broker.email or 'N/A'}",
             f"Joined: {broker.created_at.strftime('%Y-%m-%d') if broker.created_at else 'N/A'}"]

    resp.message("\n".join(lines) + "\n\n👉 Reply 'editprofile' to update your details.")
    return resp

def handle_editprofile(broker, intent, resp, msg=None):
    session = {
        "mode": "edit_broker",
        "step": "choose_field",
    }
    set_session(broker.id, session)

    resp.message(
        f"✏️ Editing Profile\n\n"
        f"What do you want to edit?\n"
        f"1️⃣ Name\n"
        f"2️⃣ Email\n\n"
        f"👉 Reply with the number"
    )
    return resp


def handle_edit_broker_session(broker, msg, resp, session):
    step = session.get("step")

    if step == "choose_field":
        field_map = {"1": "name", "2": "email"}
        if msg not in field_map:
            resp.message("⚠️ Invalid choice. Reply with 1 or 2.")
            return resp

        session["step"] = "awaiting_value"
        session["field"] = field_map[msg]
        set_session(broker.id, session)
        resp.message(f"✏️ Send me the new {session['field']}.")
        return resp

    elif step == "awaiting_value":
        field = session.get("field")
        new_value = msg.strip()

        setattr(broker, field, new_value)
        broker.save()

        clear_session(broker.id)
        resp.message(f"✅ Updated {field} to: {new_value}")
        return resp
    


def handle_new_property(broker, intent, resp, msg=None):
    desc = msg.strip()

    if not desc:
        resp.message("⚠️ Please provide a property description to add a new property.")
        return resp
    prop = extract(broker, description=desc)
    prop.status = "active"
    prop.save()

    session = {
        "mode": "new_property",
        "property_id": prop.property_id,
        "step": "awaiting_media",
        "media": []
    }
    set_session(broker.id, session)
    resp.message(
        f"✅ New Property created: [{prop.property_id}] {prop.title or 'Property'}\n\n"
        f"[{prop.property_id}] {prop.title} \n"
        f" {prop.bhk or ''} BHK in {prop.city or ''} for {prop.sale_or_rent}\n"
        f" {prop.area_sqft or 'N/A'} sqrt\n"
        f" {prop.furnishing or ''}\n"
        f" {prop.price or 'N/A'} {prop.currency}\n"
        f" near {prop.locality}\n"
        f" Status: {prop.status.title()}\n\n"
        f"👉 Reply 'list' to see all your properties\n"
        f"👉 Reply 'edit {prop.property_id}' to edit this property\n"
        f"👉 Reply 'share {prop.property_id}' to share the property\n"
        f"👉 Reply 'delete {prop.property_id}' to remove the property\n"
        f"👉 Reply 'help' for command guide"
        "📸 Now upload images/videos. Type *done* when finished, or *skip* if none."
    )
    return resp

def handle_help(broker, intent, resp, msg=None):
    resp.message(
        "*KeyMate Bot Help*\n\n"
        "Here are the commands you can use:\n\n"
        "🏡 Property Management:\n"
        "- Send property description → Add new property\n"
        "- Upload images/videos → Attach media\n"
        "- done / skip → Finish adding property\n"
        "- list → View all your properties\n"
        "- view <property_id> → View property details\n"
        "- edit <property_id> → Edit property\n"
        "- share <property_id> → Share property\n"
        "- delete <property_id> → Delete property\n"
        "- activate <property_id> → Activate property\n"
        "- disable <property_id> → Disable property\n\n"
        "👤 Profile Management:\n"
        "- profile → View your broker profile\n"
        "- editprofile → Edit your profile details\n\n"
        "❓ Help:\n"
        "- help → For your help guide"
    )
    return resp

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

def handle_disable(broker, intent, resp, msg=None):
    property_number = intent.property_id
    if not property_number:
        resp.message("⚠️ Provide a property ID. Example: 'disable 123'")
        return resp
    try: 
        prop = Property.objects.get(broker = broker, property_id=property_number)
        prop.status = "disabled"
        prop.save()
        resp.message(f"{prop.property_id} | ({prop.title}) has been Disabled.")
    except Property.DoesNotExist:
        resp.message("Property not found")
    return resp
                

def handle_delete(broker, intent, resp, msg=None):
    property_number = intent.property_id
    if not property_number:
        resp.message("⚠️ Please provide a property ID to delete. Example: 'delete 123'")
        return resp
    try: 
        prop = Property.objects.get(broker = broker, property_id=property_number)
        prop.delete()
        resp.message(f"Property {property_number} Deleted.")
    except Property.DoesNotExist:
        resp.message("Property not found")
    return resp
        

def handle_list(broker, intent, resp, msg=None):
    # parts = msg.split()
    # page = int(parts[1]) if len(parts) > 1 else 1

    page = intent.filters.get("page", 1) if intent.filters else 1
    city = intent.filters.get("city") if intent.filters else None

    qs = Property.objects.filter(broker=broker).order_by("-created_at")
    if city:
        qs = qs.filter(city__iexact=city)

    if not qs.exists():
        resp.message("⚠️ No properties found.")
        return resp
    page_size = 10
    start = (page - 1) * page_size
    end = start + page_size
    props = qs[start:end]
    properties = Property.objects.filter(broker = broker).order_by("-created_at")
    if not properties:
        resp.message("You don't have any properties yet.")
        return resp
    
    lines = []
    for p in props:
        lines.append(f"[{p.property_id}] | {p.title} | {p.city or ''} | {p.status}")

    total_pages = (qs.count() + page_size -1) // page_size

    reply_text = (
        f"📋 Your properties (Page {page}/{total_pages}):\n\n" +
                "\n".join(lines) 
        )
    if page < total_pages:
        reply_text += f"\n\n👉 Reply 'list {page+1}' for next page"
        
    resp.message(reply_text)
        
    return resp



EDIT_FIELDS_MAP = {
    "1": "price",
    "2": "city",
    "3": "bhk",
    "4": "furnishing",
    "5": "status",
}

def handle_edit(broker, intent, resp, msg=None):
    # parts = msg.split()
    # if len(parts) < 2:
    #     resp.message("Please provide a property ID. Example: edit 123")
    #     return resp

    # property_number = parts[1]

    property_id = intent.property_id
    if not property_id:
        resp.message("⚠️ Please specify which property you want to edit. Example: 'edit 123'")
        return resp
    
    try:
        prop = Property.objects.get(broker=broker, property_id=property_id)
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
        f"5️⃣ Status\n\n"
        f"👉 Reply with the number"
    )
    return resp


def handle_desc(broker, intent, resp, msg=None):
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

    url = upload_result["secure_url"]

    if resource_type == "video":
        url = url.replace("/upload/", "/upload/f_mp4/")

    return url


    

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
    prop.status = "active"
    prop.save()
    for m in media:
        MediaAsset.objects.create(property=prop, media_type=m["type"], storage_url=m["url"], order=m["order"])

    clear_session(broker.id)
    resp.message(
        f" New property added.\n\n"
        f"[{prop.property_id}] {prop.title} \n"
        f" {prop.bhk or ''} BHK in {prop.city or ''} for {prop.sale_or_rent}\n"
        f" {prop.area_sqft or 'N/A'} sqrt\n"
        f" {prop.furnishing or ''}\n"
        f" {prop.price or 'N/A'} {prop.currency}\n"
        f" near {prop.locality}\n"
        f" Status: {prop.status.title()}\n\n"
        f"👉 Reply 'list' to see all your properties\n"
        f"👉 Reply 'edit {prop.property_id}' to edit this property\n"
        f"👉 Reply 'share {prop.property_id}' to share the property\n"
        f"👉 Reply 'delete {prop.property_id}' to remove the property\n"
        f"👉 Reply 'help' for command guide"
    )
    return resp

def handle_view(broker, intent, resp, msg=None):
    property_id = intent.property_id
    # parts = msg.split()
    # if len(parts) < 2:
    #     resp.message("⚠️ Please provide a property ID. Example: view 123")
    #     return resp



    # property_number = parts[1]
    if not property_id:
        resp.message("⚠️ Please provide a property ID. Example: view 123")
        return resp
    

    try:
        prop = Property.objects.get(broker=broker, property_id=property_id)
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
    if media_assets.exists():
        msg_with_media = resp.message("📸 Property Media")
        for media in media_assets:
            if media.media_type == "image":
                msg_with_media = resp.message("📸 Property Image")
                msg_with_media.media(media.storage_url)
            elif media.media_type == "video":
                msg_with_media = resp.message("🎥 Property Video")
                msg_with_media.media(media.storage_url)

    return resp



#whatsapp sharing
def handle_share(broker, intent, resp, msg = None):
    # parts = msg.split()
    # if len(parts) <2 :
    #     resp.message("⚠️ Please provide a property ID. Example: share 123")
    #     return resp
    
    # property_number = parts[1]

    property_id = intent.property_id
    if not property_id:
        resp.message("⚠️ Please specify a property to share. Example: 'share 123'")
        return resp

    try:
        prop = Property.objects.get(broker= broker, property_id = property_id)
    except Property.DoesNotExist:
        resp.message("❌ Property Not Found.")
        return resp
    
    generated_text = generate_property_message(prop, broker)

    media_assets = MediaAsset.objects.filter(property=prop)

    msg_with_media = resp.message(generated_text)
    for media in media_assets:
        if media.media_type == "image":
            msg_with_media = resp.message("📸 Property Image")
            msg_with_media.media(media.storage_url)
        elif media.media_type == "video":
            msg_with_media = resp.message("🎥 Property Video")
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
            resp = handle_onboarding(phone, msg, resp)
            return HttpResponse(str(resp), content_type="application/xml")


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
                    new_value = msg.strip().lower()

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

            elif session.get("mode") == "edit_broker": 
                resp = handle_edit_broker_session(broker, msg, resp, session)
                return HttpResponse(str(resp), content_type="application/xml")


        COMMANDS = {
            "disable": handle_disable,
            "delete": handle_delete,
            "list": handle_list,
            "edit": handle_edit,
            "view": handle_view,
            "help": handle_help,
            "profile": handle_profile,
            "editprofile": handle_editprofile,
            "share": handle_share

        }

        for cmd, handler in COMMANDS.items():
            if msg.lower().startswith(cmd):
                resp = handler(broker, msg, resp)
                return HttpResponse(str(resp), content_type="application/xml")


            

        resp = handle_desc(broker, msg, resp)

        return HttpResponse(str(resp), content_type = "application/xml")
    

    return HttpResponse("Invalid request", status=400)

