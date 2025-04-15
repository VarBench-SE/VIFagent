from vif_agent.agent import VifAgent
from openai import OpenAI
from vif_agent.renderer.tex_renderer import TexRenderer
import os


def test_appply_instruction():

    client = OpenAI(
        api_key=os.environ.get("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1",
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
        model="meta-llama/llama-4-maverick-17b-128e-instruct",
        temperature=0.0,
        identification_client=identification_client,
        identification_model="gemini-2.0-flash",
        identification_model_temperature=0.3,
        search_client=search_client,
        search_model="gemini-2.0-flash",
        search_model_temperature=0.0,
        debug=True,
    )

    plane_tex = open("tests/resources/plane.tex").read()
    commented_code = agent.apply_instruction(
        plane_tex,
        "Add a second plane Pi_2, parallel to the x-y-plane. This plane should intersect with the existing plane, and their intersection should cross the z-axis.",
    )

    with open("applied_plane.tex", "w") as md_chimp:
        md_chimp.write(commented_code)


def main():
    test_appply_instruction()


if __name__ == "__main__":
    main()
