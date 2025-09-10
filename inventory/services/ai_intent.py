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