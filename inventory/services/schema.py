from pydantic import BaseModel, Field
from typing import List, Optional

class PropertySchema(BaseModel):
    title: Optional[str] = Field(None, description="Short title of the property, its should be unique and creative, don't include city or number of bhk or any other editable details, just a creative title which also have correct spellings")
    description_beautified: Optional[str] = Field(None, description="Polished client-facing description")
    city: Optional[str]
    locality: Optional[str]
    bhk: Optional[int]
    bathrooms: Optional[int]
    area_sqft: Optional[float]
    floor: Optional[int]
    total_floors: Optional[int]
    furnishing: Optional[str] = Field(None, description="Unfurnished, Semi-Furnished, Fully-Furnished")
    age_of_property: Optional[int]
    amenities: Optional[List[str]] = Field(None, description="all the amenties  like Gym, Pool and many more")
    sale_or_rent: Optional[str] = Field(None, description="Sale or Rent")
    price: Optional[float]
    currency: Optional[str] = "INR"
    maintenance: Optional[float]
    deposit: Optional[float]
    source: Optional[str] = Field(None, description=" mark as Direct if its broker's property or if the property is from other broker then marked as other broker")
    source_broker_name: Optional[str]
    source_broker_phone: Optional[int]