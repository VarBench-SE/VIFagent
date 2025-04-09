from vif_agent.agent import VifAgent
from openai import OpenAI
from vif_agent.renderer.tex_renderer import TexRenderer
import os


def test_chimpanzee_comment():

    client = OpenAI(
        api_key=os.environ.get("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1"
    )

    identification_client = OpenAI(
        api_key=os.environ.get("GOOGLE_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    search_client = OpenAI(
        api_key=os.environ.get("GOOGLE_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    agent = VifAgent(
        TexRenderer().from_string_to_image,
        client=client,
        model="llama-3.3-70b-versatile",
        temperature=0.0,
        identification_client=identification_client,
        identification_model="gemini-2.0-flash",
        identification_model_temperature=0.3,
        search_client=search_client,
        search_model="gemini-2.0-flash",
        search_model_temperature=0.0,
        debug=True
    )

    chimp_tex = open("tests/resources/plane.tex").read()
    commented_code = agent.identify_features(chimp_tex)
    #modified_code = agent.apply_instruction(dog_tex, "Make the eyes of the chimpanzee crossed, by making them white and adding black pupils")

    with open("commented_plane.tex", "w") as md_chimp:
        md_chimp.write(commented_code)


def main():
    test_chimpanzee_comment()

if __name__ =="__main__":
    main()