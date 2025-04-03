#labels must be a list
DETECTION_PROMPT: str = """Detect, with no more than 20 items. Output a json list where each entry contains the 2D bounding box in "box_2d" and {labels} in "label"."""
FEATURE_IDENTIFIER_PROMPT:str = """Give me a json describing the image
The first field description contains a high-level description of the image.  
The second field features contains a list of up to 20 specific features.
Notes: 
- Each feature MUST have a precise name, preferably with position and color attributes.  
- High-level features CAN be described in one to five words (e.g., objects, things, or specific elements in the image).  
- the json MUST be between code blocks.
- You MUST follow the exact pattern below.

Output format:
```json
{
  "description": "high-level description",
  "features": [
    "feature1",
    "feature2",
    "feature3",
    ...
  ]
}
```
"""

SYSTEM_PROMPT_GENERATION: str = """
You are an expert coding assistant specialized in modifying file contents based on instructions.
Given an instruction and file content, respond only with the updated file's full content, ensuring it is entirely enclosed between code tags like this
```
content
```

Provide no additional text or explanations beyond the code tags.
"""

IT_PROMPT: str = """
{instruction}
```
{content}
```
"""