import os
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from .schema import PropertySchema
from inventory.models import Property, MediaAsset
from dotenv import load_dotenv

load_dotenv()

def generate_property_message(prop, broker):
    model = ChatGroq(
        model = "llama-3.3-70b-versatile",
        temperature = 0.7
    )

    bhk_display = f"{prop.bhk} BHK" if prop.bhk else ""
    if prop.bhk == 1 and (
        "studio" in (prop.title or "").lower() 
        or "studio" in (prop.description_raw or "").lower()
    ):
        bhk_display = "1 RK"

    details = []
    if prop.title:
        details.append(f"🏡 {prop.title}")
    if bhk_display:
        details.append(f"{bhk_display}")
    if prop.area_sqft:
        details.append(f"Area: {prop.area_sqft} sq.ft.")
    if prop.price:
        details.append(f"Price: {prop.price} {prop.currency or ''}")
    if prop.maintenance:
        details.append(f"Price: {prop.maintenance} {prop.currency or ''}")
    if prop.deposit:
        details.append(f"Price: {prop.deposit} {prop.currency or ''}")
    if prop.sale_or_rent:
        details.append(f"Type: {prop.sale_or_rent.title()}")
    if prop.city or prop.locality:
        details.append(f"Location: {prop.locality or ''}, {prop.city or ''}")
    if prop.furnishing:
        details.append(f"Furnishing: {prop.furnishing}")
    if prop.amenities:
        details.append(f"Amenities: {prop.amenities}")

    details_text = "\n".join(details)

    prompt = f"""Create a clear, structured WhatsApp message to share a property with buyers. 
    Keep it professional, use minimal emojis (only where suitable), and make it easy to read. 
    Use bullet points for clarity.

    Property Details:
    {details_text}

    At the end, add a closing signature like:
    ---
    Contact Broker:
    {broker.name} ({broker.phone_number})"""

    response = model.invoke(prompt)
    return response.content



    