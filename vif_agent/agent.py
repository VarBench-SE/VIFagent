import os
import shutil
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
import uuid
import sys
logger.remove()
logger.add(sys.stderr, level="INFO")


class VifAgent:
    def __init__(
        self,
        code_renderer: Callable[[str], Image.Image],
        client: OpenAI,
        model: str,
        temperature: float = 0.0,
        search_client: OpenAI = None,
        search_model: str = None,
        search_model_temperature=None,
        identification_client: OpenAI = None,
        identification_model: str = None,
        identification_model_temperature=0.3,
        debug=False,
        debug_folder=".tmp/debug",
    ):
        self.client = client
        self.model = model
        self.code_renderer = code_renderer
        self.temperature = temperature
        self.identification_model_temperature = identification_model_temperature
        self.debug = debug
        self.debug_folder = debug_folder

        self.search_client = search_client or client
        self.search_model_temperature = search_model_temperature or temperature
        self.identification_client = identification_client or client
        self.search_model = search_model or model
        self.identification_model = identification_model or model

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
        self.debug_id = str(uuid.uuid4())
        os.mkdir(os.path.join(self.debug_folder, self.debug_id))
        # unifying the code for easier parsing in mutant creation
        code = "\n".join(line.strip() for line in code.split("\n"))
        # render image
        base_image = self.code_renderer(code)
        # VLM to get features
        logger.info("Searching for features")
        encoded_image = encode_image(image=base_image)
        response = self.search_client.chat.completions.create(
            model=self.search_model,
            temperature=self.search_model_temperature,
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
        search_match = re.search(pattern, response.choices[0].message.content)
        if not search_match:
            logger.warning(
                f"Feature search failed, using un-commented code, unparseable response {response.choices[0].message.content}"
            )
            return code

        features_match = search_match.group(1)
        features = json.loads(features_match)
        """DEBUG"""
        if self.debug:
            json.dump(
                features,
                open(
                    os.path.join(self.debug_folder, self.debug_id, "features.json"), "w"
                ),
            )
        """"""
        # Segmentation via google ai spatial
        logger.info("Identifying features")
        response = self.identification_client.chat.completions.create(
            model=self.identification_model,
            temperature=self.identification_model_temperature,
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
        id_match = re.search(pattern, response.choices[0].message.content)

        if not id_match:
            logger.warning(
                f"Feature identification failed, using un-commented code, unparseable response {response.choices[0].message.content}"
            )
            return code

        json_boxes = id_match.group(1)
        detected_boxes = json.loads(json_boxes)
        detected_boxes = [adjust_bbox(box, base_image) for box in detected_boxes]
        """DEBUG"""
        if self.debug:
            json.dump(
                detected_boxes,
                open(os.path.join(self.debug_folder, self.debug_id, "boxes.json"), "w"),
            )
        """"""
        # create mutants of the code
        mutant_creator = TexRegMutantCreator()
        mutants = mutant_creator.create_mutants(code)

        # Check what has been modified by each mutant
        char_id_feature: dict = (
            {}
        )  # mapping between the character index and the detected feature
        """DEBUG"""
        if self.debug:
            base_image.save(
                os.path.join(self.debug_folder, self.debug_id, "base_image.png")
            )
            shutil.rmtree(
                os.path.join(self.debug_folder, self.debug_id, "features/"),
                ignore_errors=True,
            )
            os.mkdir(os.path.join(self.debug_folder, self.debug_id, "features"))
        """"""
        for box in detected_boxes:
            base_image_mask = base_image.crop(box["box_2d"])
            """DEBUG"""
            if self.debug:
                base_image_mask.save(
                    os.path.join(
                        self.debug_folder,
                        self.debug_id,
                        "features/" + box["label"] + ".png",
                    )
                )
            """"""
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
        """DEBUG"""
        if self.debug:
            with open(
                os.path.join(self.debug_folder, self.debug_id, "commented_code.tex"),
                "w",
            ) as annot:
                annot.write(annotated_code)
        """"""
        return annotated_code

    def __str__(self):
        return (
            f"VifAgent(model={self.model}, temperature={self.temperature}, "
            f"search_model={self.search_model}, search_model_temperature={self.search_model_temperature}, "
            f"identification_model={self.identification_model}, identification_model_temperature={self.identification_model_temperature}, "
            f"debug={self.debug}, debug_folder='{self.debug_folder}')"
        )
