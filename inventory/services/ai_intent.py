from pydantic import BaseModel, Field
from typing import Optional, Dict
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
import os

class UserIntent(BaseModel):
    action: str = Field(
        ...,
        description="The action the user wants to perform. Possible values: new_property, list_properties, view_property, share_property, edit_property, delete_property, activate_property, disable_property, profile, editprofile, help."
    )
    property_id: Optional[str] = Field(
        None,
        description="The unique ID of the property if the user explicitly refers to one. Required for view_property, share_property, edit_property, delete_property, activate_property, and disable_property."
    )
    filters: Optional[Dict] = Field(
        default_factory=dict,
        description="Search filters when listing properties, such as {'city': 'Pune', 'price': '<=5000000'}."
    )

model = ChatGroq(
    model = "llama-3.3-70b-versatile",
    temperature = 0
)

parser = PydanticOutputParser(pydantic_object=UserIntent)

prompt = PromptTemplate(
    template=(
        """
        You are an intent classifier for a real estate WhatsApp bot.
        User message: {user_msg}\n\n
        Decide what the user wants.
        Possible actions:\n
        - list_properties (with optional filters like city, price)\n
        - view_property (requires property_id)\n
        - share_property (requires property_id)\n
        - share_all_to_client (requires filters + client_number)\n
        - edit_property (requires property_id)\n
        - delete_property (requires property_id)\n
        - activate_property (requires property_id)\n
        - disable_property (requires property_id)\n
        - profile\n
        - editprofile\n
        - help\n\n

        If the message looks like a property description (location, rent, deposit, bhk, etc.),
        then classify as 'new_property'.
        Output in JSON following this schema:\n{format_instructions}
        """
    ),
    input_variables=["user_msg"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)


chain = prompt | model | parser

def classify_intent(user_msg : str) -> UserIntent:
    result = chain.invoke({"user_msg": user_msg})
    return result


##for customer

class CustomerIntent(BaseModel):
    action: str = Field(..., description="The action the customer wants to perform. Possible values: list_properties, view_property, contact_broker, help.")
    property_id: Optional[str] = Field(None, description="The unique ID of the property if the customer explicitly refers to one. Required for view_property and contact_broker.")
    filters: Optional[dict] = Field(default_factory=dict, description="Search filters when listing properties, such as {'city': 'Mumbai'}.")


customer_parser = PydanticOutputParser(pydantic_object=CustomerIntent)

customer_prompt = PromptTemplate(
    template=(
        """
        You are an intent classifier for a customer-facing real estate WhatsApp bot.
        User message: {user_msg}\n\n
        Decide what the user wants.
        Possible actions:\n
        - list_properties (with optional filters like city, price, bhk)\n
        - view_property (requires property_id)\n
        - help\n\n

        If the user message looks like they are asking for apartments/houses,
        but didn't use keywords 'view' or 'list', classify as 'list_properties'
        and extract filters such as city, price, bhk from the text.

        If the user explicitly gives a property ID like 'view 123',
        classify as 'view_property' and set property_id.

        Output in JSON following this schema:\n{format_instructions}
        """
    ),
    input_variables=["user_msg"],
    partial_variables={"format_instructions": customer_parser.get_format_instructions()},
)

customer_chain = customer_prompt | model | customer_parser

def classify_customer_intent(user_msg: str)-> CustomerIntent:
    result = customer_chain.invoke({"user_msg": user_msg})
    return result