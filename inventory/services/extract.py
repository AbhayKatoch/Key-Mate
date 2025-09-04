import os
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from .schema import PropertySchema
from inventory.models import Property, MediaAsset
from dotenv import load_dotenv

load_dotenv()

model = ChatGroq(
    model = "llama-3.3-70b-versatile",
    temperature = 0
)

parser = PydanticOutputParser(pydantic_object=PropertySchema)

prompt = ChatPromptTemplate([
    ("system", "You are a real estate data normalizer. Extract structured details from broker property descriptions."),
    ("human", "Description: {description} {format_instructions}\n\nReturn JSON in the format required by PropertySchema.")
])

chain = prompt | model | parser


def extract(broker, description: str, media_urls = None):
    result = chain.invoke({
        "description": description,
        "format_instructions": parser.get_format_instructions()
    })

    property_obj = Property.objects.create(
        broker=broker,
        title=result.title or f"{result.bhk}BHK in {result.city or 'Unknown'}",
        description_beautified=result.description_beautified,
        city=result.city,
        locality=result.locality,
        bhk=result.bhk,
        bathrooms=result.bathrooms,
        area_sqft=result.area_sqft,
        floor=result.floor,
        total_floors=result.total_floors,
        furnishing=result.furnishing,
        age_of_property=result.age_of_property,
        sale_or_rent=result.sale_or_rent or "rent",
        price=result.price,
        currency=result.currency,
        maintenance=result.maintenance,
        deposit=result.deposit,
        amenities=result.amenities,
        source=result.source,
        source_broker_name=result.source_broker_name,
        source_broker_phone=result.source_broker_phone,

    )

    if media_urls:
        for url in media_urls:
            MediaAsset.objects.create(property=property_obj, storage_url = url)

    return property_obj        



