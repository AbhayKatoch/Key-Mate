from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from twilio.twiml.messaging_response import MessagingResponse
from urllib.parse import parse_qs
from inventory.models import Broker, Property, MediaAsset
from inventory.services.redis_setup import get_session, set_session, clear_session
from inventory.services.sharing_msg import generate_property_message
from langchain.agents import initialize_agent, Tool
from langchain_groq import ChatGroq
from inventory.services.redis_setup import set_session, get_session, clear_session


def list_properties(broker_id, filters = None):
    qs = Property.objects.filter(broker_id = broker_id)
    if filters:
        if "status" in filters:
            qs = qs.filter(status__iexact = filters["status"])
        
        if "city" in filters:
            qs = qs.filter(city__icontains = filters["city"])

    if not qs.exists():
        return "No properties found"
    return "\n".join([f"[{p.property_id}] {p.title or 'Untitled'} | {p.city or ''} | {p.status}" for p in qs]) 
    


def view_property(broker_id, property_id):
    try:
        p = Property.objects.get(broker_id=broker_id, property_id= property_id)
    except Property.DoesNotExist:
        return "Property Not Found."
    
    details = [
        f"🏠 [{p.property_id}] {p.title or ''}",
        f"Price: {p.price or 'N/A'} {p.currency or ''}",
        f"Type: {p.sale_or_rent or ''}",
        f"City: {p.city or ''}",
        f"Locality: {p.locality or ''}",
        f"Area: {p.area_sqft or 'N/A'} sqft",
        f"BHK: {p.bhk or ''}",
        f"Furnishing: {p.furnishing or ''}",
        f"Status: {p.status or ''}"
    ]
    return "\n".join(details)

def update_property_status(broker_id, property_id, status):
    try:
        prop = Property.objects.get(broker_id = broker_id, property_id = property_id)
        prop.status = status
        prop.save()
        return f"Property {property_id} updated to {status}"
    
    except Property.DoesNotExist:
        return f"Property {property_id} not found."
    
def delete_property(broker_id, property_id):
    try:
        prop = Property.objects.get(broker_id = broker_id, property_id = property_id)
        prop.delete()
        return f"Property {property_id} deleted"
    except Property.DoesNotExist:
        return "Property Not Found."
    
def generate_share_message(broker_id, property_id):
    try:
        prop = Property.objects.get(broker_id=broker_id, property_id=property_id)
    except Property.DoesNotExist:
        return "❌ Property not found."
    return generate_property_message(prop, prop.broker)

def get_broker_profile(broker_id):
    broker = Broker.objects.get(id=broker_id)
    return f"👤 {broker.name} | {broker.phone_number} | {broker.email or 'N/A'}"


tools = [
    Tool(name="list_properties", func=lambda broker_id, filters = None: list_properties(broker_id, filters), description="List broker's properties. Optionally filter by status or city."),
    Tool(name="view_property", func=lambda broker_id, property_id: view_property(broker_id, property_id),
         description="View detailed info of a property by property_id."),
    Tool(name="update_property_status", func=lambda broker_id, property_id, status: update_property_status(broker_id, property_id, status),
         description="Update a property's status (active/disabled)."),
    Tool(name="delete_property", func=lambda broker_id, property_id: delete_property(broker_id, property_id),
         description="Delete a property by ID."),
    Tool(name="generate_share_message", func=lambda broker_id, property_id: generate_share_message(broker_id, property_id),
         description="Generate a shareable buyer-friendly message for a property."),
    Tool(name="get_broker_profile", func=lambda broker_id: get_broker_profile(broker_id),
         description="View broker profile details."),
]

model = ChatGroq(
    model = "llama-3.3-70b-versatile",
    temperature = 0
)

agent = initialize_agent(tools, model, agent="chat-conversational-react-description", verbose = True)

@csrf_exempt
def whatsaap_webhook(request):
    if request.method == "POST":
        body = request.body.decode("utf-8")
        data = parse_qs(body)
        msg = data.get("Body", [""])[0]
        from_number = data.get("From", [""])[0]

        phone = from_number.replace("whatsapp:", "")
        resp = MessagingResponse()

        try:
            broker = Broker.objects.get(phone_number=phone)
        except Broker.DoesNotExist:
            resp.message("👋 Welcome to KeyMate! Please register first. Send your *full name* to start.")
            return HttpResponse(str(resp), content_type="application/xml")

        session = get_session(broker.id) or {}
        history = session.get("chat_history", [])


        try:
            answer = agent.invoke({"input": msg, "broker_id": broker.id, "chat_history": history})

            history.append(("user", msg))
            history.append(("assistant", answer))
            session["chat_history"] = history
            set_session(broker.id, session)
            resp.message(answer)
        except Exception as e:
            resp.message("⚠️ Sorry, something went wrong. Please try again.")
            print("Agent error:", e)

        return HttpResponse(str(resp), content_type="application/xml")

    return HttpResponse("Invalid request", status=400)
