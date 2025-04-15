import os
import shutil
from typing import Iterable
from openai import OpenAI
from collections.abc import Callable
from PIL import Image
from sentence_transformers import SentenceTransformer
from vif_agent.feature import CodeImageMapping, MappedCode
from vif_agent.mutation.mutant import TexMutant
from vif_agent.utils import adjust_bbox, encode_image, mse
from vif_agent.prompt import *
from vif_agent.mutation.tex_mutant_creator import (
    TexMappingMutantCreator,
    TexRegBrutalMutantCreator,
    TexRegMutantCreator,
    TexMutantCreator,
)
import json
import re
from functools import cache
from loguru import logger
import uuid
import sys

type Spans = tuple[list[tuple[int, int]], float]  # for lisibiilty

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
        clarify_instruction=True,
        debug_folder=".tmp/debug",
        mutant_creator=TexMappingMutantCreator(),
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

        self.clarify_instruction = clarify_instruction

        self.mutant_creator = mutant_creator
        
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

    def apply_instruction(self, code: str, instruction: str):
        """DEBUG"""
        if self.debug:
            self.debug_id = str(uuid.uuid4())
            os.mkdir(os.path.join(self.debug_folder, self.debug_id))
        """"""
        feature_map = self.identify_features(code)
        annotated_code = self.annotate_code(code, feature_map)

        base_image = self.code_renderer(code)

        user_instruction = IT_PROMPT.format(
            instruction=instruction, content=annotated_code
        )

        if self.apply_clarification:
            logger.info("clarifying the instruction")
            instruction = self.apply_clarification(instruction, base_image)

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

    def apply_clarification(self, instruction: str, base_image: Image.Image):
        encoded_image = encode_image(image=base_image)

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT_CLARIFY,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": instruction,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            },
                        },
                    ],
                },
            ],
        )

        new_instruction = response.choices[-1].message.content
        if self.debug:
            open(
                os.path.join(self.debug_folder, self.debug_id, "new_instruction.txt"),
                "w",
            ).write(new_instruction)

        return new_instruction

    def identify_features(self, code: str) -> MappedCode:
        """Identifies the features within the code by commenting it

        Args:
            code (str): The code where the features need to be identified
            comment_character (str): the character used to comment the code
        Returns:
            dict[str, list[Spans]]: a dictionnary associating the feature with a list of probable spans
        """
        """DEBUG"""
        if self.debug and not hasattr(self, "debug_id"):
            self.debug_id = str(uuid.uuid4())
            os.mkdir(os.path.join(self.debug_folder, self.debug_id))
        """"""

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
            return code, base_image

        features_match = search_match.group(1)
        features = json.loads(features_match)
        self.features = features
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
            return code, base_image

        json_boxes = id_match.group(1)
        detected_boxes = json.loads(json_boxes)
        detected_boxes = [adjust_bbox(box, base_image) for box in detected_boxes]
        self.detected_boxes = detected_boxes
        """DEBUG"""
        if self.debug:
            json.dump(
                detected_boxes,
                open(os.path.join(self.debug_folder, self.debug_id, "boxes.json"), "w"),
            )
        """"""
        # create mutants of the code
        mutants = self.mutant_creator.create_mutants(code)

        # Check what has been modified by each mutant
        feature_map: dict[str, list[tuple[CodeImageMapping, float]]] = (
            {}
        )  # mapping between the feature and a list of possible spans of the part of the code of the feature and their "probability" of being the right span
        
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
            cur_mse_map: list[tuple[float, TexMutant]] = []
            for mutant in mutants:
                mutant_image_mask = mutant.image.crop(box["box_2d"])
                cur_mse_map.append((mse(base_image_mask, mutant_image_mask), mutant))

            sorted_mse_map: list[tuple[float, TexMutant]] = sorted(
                filter(lambda m: m[0] != 0, cur_mse_map),
                key=lambda m: m[0],
                reverse=True,
            )
            
            mappings_for_features: list[tuple[CodeImageMapping, float]] = [
                (CodeImageMapping(mutant.deleted_spans,box["box_2d"]), mse_value)
                for mse_value, mutant in sorted_mse_map
            ]
            
            feature_map[box["label"]] = mappings_for_features

            mapped_code = MappedCode(base_image,code,feature_map,self.embedding_model)
        return mapped_code

        


    def __str__(self):
        return (
            f"VifAgent(model={self.model}, temperature={self.temperature}, "
            f"search_model={self.search_model}, search_model_temperature={self.search_model_temperature}, "
            f"identification_model={self.identification_model}, identification_model_temperature={self.identification_model_temperature}, "
            f"debug={self.debug}, debug_folder='{self.debug_folder}')"
        )
