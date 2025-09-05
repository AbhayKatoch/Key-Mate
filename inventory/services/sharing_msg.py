import os
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from .schema import PropertySchema
from inventory.models import Property, MediaAsset
from dotenv import load_dotenv

load_dotenv()

def generate_property_message(prop):
    model = ChatGroq(
        model = "llama-3.3-70b-versatile",
        temperature = 0.7
    )

    details = (
        f"Property ID: {prop.property_id}\n"
        f"Title: {prop.title}\n"
        f"Type: {prop.sale_or_rent}\n"
        f"Price: {prop.price} {prop.currency or ''}\n"
        f"Location: {prop.city}, {prop.locality}\n"
        f"Area: {prop.area_sqft} sqft\n"
        f"BHK: {prop.bhk}\n"
        f"Furnishing: {prop.furnishing}\n"
        f"Amenities: {prop.amenities}\n"
    )

    prompt = f"""Create a professional and attractive WhatsApp message for a potential buyer.
    Keep it short, engaging, and highlight the key selling points.
    Add a few relevant emojis for appeal.
    Property Details:
    {details}"""

    response = model.invoke(prompt)
    return response.content



    