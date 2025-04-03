#labels must be a list
DETECTION_PROMPT: str = """Detect, with no more than 20 items. Output a json list where each entry contains the 2D bounding box in "box_2d" and {labels} in "label"."""
FEATURE_IDENTIFIER_PROMPT:str = """List, with no more than 20 items, each individual specific feature of the image in a json array, where each feature contains a precise name making it identifiable, preferably with a position and color attribute. Preferably describe high level features in one to five words, like object, things or specific things in the image. """

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