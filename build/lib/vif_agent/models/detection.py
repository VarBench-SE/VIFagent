from typing import List
from pydantic import BaseModel, conlist, Field
from typing import Annotated


class BoxDetections(BaseModel):
    boxes:List[int]

class BoxDetection(BaseModel):
    box_2d: Annotated[List[int],Field(min_items=4, max_items=4)]
    label: str
    

class Features(BaseModel):
    image_description:Annotated[str,Field(description="detailed description of the image")]
    features: Annotated[list[str],Field(description="Name of each individual feature")]