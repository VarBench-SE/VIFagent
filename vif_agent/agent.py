from typing import Iterable
from openai import OpenAI
from collections.abc import Callable
from PIL import Image
from vif_agent.utils import adjust_bbox, encode_image, mse
from vif_agent.prompt import *
from vif_agent.mutation.tex_mutant_creator import TexRegMutantCreator
import json
import re
from functools import cache
from loguru import logger


class VifAgent:
    def __init__(
        self,
        code_renderer: Callable[[str], Image.Image],
        client: OpenAI,
        model: str,
        search_client: OpenAI = None,
        search_model: str = None,
        identification_client: OpenAI = None,
        identification_model: str = None,
        temperature: float = 0,
    ):
        self.client = client
        self.model = model
        self.code_renderer = code_renderer
        self.temperature = temperature
        if not search_client:
            self.search_client = client
        else:
            self.search_client = search_client
        if not identification_client:
            self.identification_client = client
        else:
            self.identification_client = identification_client
        if not search_model:
            self.search_model = model
        else:
            self.search_model = search_model
        if not identification_model:
            self.identification_model = model
        else:
            self.identification_model = identification_model

    def apply_instruction(self, code: str, instruction: str):
        annotated_code = self.identify_features(code)
        user_instruction = IT_PROMPT.format(
            instruction=instruction, content=annotated_code
        )
        logger.info("applying the instruction")
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT_GENERATION,
                },
                {"role": "user", "content": user_instruction},
            ],
        )
        return response.choices[-1].message.content

    @cache
    def identify_features(self, code: str, comment_character: str = "%") -> str:
        """Identifies the features within the code by commenting it

        Args:
            code (str): The code where the features need to be identified
            comment_character (str): the character used to comment the code
        Returns:
            str: The new code, commented with the appropriate features
        """
        # unifying the code for easier parsing in mutant creation
        code = "\n".join(line.strip() for line in code.split("\n"))
        # render image
        base_image = self.code_renderer(code)
        # VLM to get features
        logger.info("Searching for features")
        encoded_image = encode_image(image=base_image)
        response = self.search_client.chat.completions.create(
            model=self.search_model,
            temperature=self.temperature,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": FEATURE_IDENTIFIER_PROMPT,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            },
                        },
                    ],
                }
            ],
        )
        pattern = r"```(?:\w+)?\n([\s\S]+?)```"
        match = re.search(pattern, response.choices[0].message.content)
        features_match = match.group(1)
        features = json.loads(features_match)
        # Segmentation via google ai spatial
        logger.info("Identifying features")
        response = self.identification_client.chat.completions.create(
            model=self.identification_model,
            temperature=self.temperature,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": DETECTION_PROMPT.format(
                                labels=", ".join(features["features"])
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            },
                        },
                    ],
                }
            ],
        )
        pattern = r"```(?:\w+)?\n([\s\S]+?)```"
        match = re.search(pattern, response.choices[0].message.content)

        json_boxes = match.group(1)
        detected_boxes = json.loads(json_boxes)
        detected_boxes = [adjust_bbox(box, base_image) for box in detected_boxes]
        # create mutants of the code

        mutant_creator = TexRegMutantCreator()
        mutants = mutant_creator.create_mutants(code)

        # Check what has been modified by each mutant
        char_id_feature: dict = (
            {}
        )  # mapping between the character index and the detected feature
        # TODO remove => debug
        # base_image.save(".tmp/base_image.png")
        # shutil.rmtree(".tmp/features/", ignore_errors=True)
        # os.mkdir(".tmp/features")

        for box in detected_boxes:
            base_image_mask = base_image.crop(box["box_2d"])
            # TODO remove => debug
            # base_image_mask.save(".tmp/features/" + box["label"] + ".png")
            cur_mse_map: list = []
            for mutant, mutant_image, char_number in mutants:
                mutant_image_mask = mutant_image.crop(box["box_2d"])
                cur_mse_map.append(
                    (
                        mse(base_image_mask, mutant_image_mask),
                        (mutant, mutant_image, char_number),
                    )
                )
            sorted_mse_map = sorted(
                filter(lambda mutant: mutant[0] != 0, cur_mse_map),
                key=lambda mutant: mutant[0],
                reverse=True,
            )
            for mse_value, mutant in sorted_mse_map:
                features_for_char: list = char_id_feature.get(mutant[2], [])
                features_for_char.append((box["label"], mse_value))
                char_id_feature[mutant[2]] = sorted(
                    features_for_char, key=lambda x: x[1], reverse=True
                )  # order the labels by the mse, the features that modify selected box the most are kept

        annotated_code = code
        # Annotate the code
        for characted_index, labels in sorted(char_id_feature.items(), reverse=True):
            labels = [label[0] for label in labels]  # removing the mse
            if len(labels) == len(
                detected_boxes
            ):  # all features have been detected for the modifications of this mutant, skipping
                continue
            selected_features = ", ".join(labels[:2])  #
            annotated_code = (
                annotated_code[:characted_index]
                + "\n"
                + comment_character
                + selected_features
                + annotated_code[characted_index:]
            )
        annotated_code = (
            comment_character + features["description"] + "\n" + annotated_code
        )
        return annotated_code
