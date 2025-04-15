# VIFagent
VIsual and Feature-based agent for code customization 

## Overview

Upon receiving an instruction a code, the VIF-agent workflow acts in three steps:
- Search: The search model receives an image and lists all the features in it.
- Identification: 
  - The features are given to the identification model, that return bounding boxes for each feature.
  - A list of mutants are created from the initial code(by removing random commands).
  - Mutants that modify the image within the bounding boxes are associated with the features.
  - The lines modified by each mutant are annotated by commenting the associated feature(s)
- Customization: The commented code is now given with the instruction to the customization model(named simply model), that customizes the code according to the instruction.NOTE: this customization step will probably be enhanced with an agentic workflow(using tool and iterative refinement)

## Get Started

```py
from agent import VifAgent
from renderer.tex_renderer import TexRenderer
from openai import OpenAI

identification_client = OpenAI(
    api_key="YOUR_KEY",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
search_client = OpenAI(
    api_key="YOUR_KEY",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
client = OpenAI(api_key="YOUR_KEY")


agent = VifAgent(
    TexRenderer().from_string_to_image,
    client=client,
    model="gpt-4o-2024-08-06",
    identification_client=identification_client,
    identification_model="gemini-2.0-flash",
    search_client=search_client,
    search_model="gemini-2.0-flash",
    temperature=0
)


shark_tex = open("shark.tex").read()

modified_code = agent.apply_instruction(shark_tex, "remove the teeth of the shark")

with open("modified_shark.tex", "w") as md_shark:
    md_shark.write(modified_code)

```

### Identify Features


```python
mapped_code = agent.identify_features(shark_tex)

#Get the commented code from the mapped code
commented_code = mapped_code.get_commented()

with open("commented_shark.tex", "w") as md_chimp:
   md_chimp.write(commented_code)

#get mappings from a string
mappings = mapped_code.get_cimappings("ears")
```

`mapped_code` represents a code in which each feature has been "identified", It contains a mapping from a feature name to a list of parts of the code where the feature could be(and a probability)