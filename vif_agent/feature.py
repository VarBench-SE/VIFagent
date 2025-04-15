from dataclasses import dataclass
from PIL import Image

from sentence_transformers import SentenceTransformer

type Box2D = tuple[float, float, float, float]
type Span = tuple[int, int]


@dataclass
class CodeImageMapping:
    """code to image mapping"""

    spans: list[Span]
    zone: Box2D


class MappedCode:
    def __init__(
        self,
        image: Image.Image,
        code: str,
        feature_map: dict[str, list[tuple[CodeImageMapping, float]]],
        embedding_model: SentenceTransformer,
    ):
        self.image = image
        self.code = code
        self.feature_map = feature_map
        self.embedding_model = embedding_model

        self.key_embeddings = embedding_model.encode(list(self.feature_map.keys()))

    def get_commented(self, comment_character: str = "%") -> str:
        char_id_feature: dict = (
            {}
        )  # mapping between the character index and the detected feature

        for feature_name, prob_mappings in self.feature_map.items():
            for mapping, prob in prob_mappings:
                features_for_char: list = char_id_feature.get(
                    mapping.spans[0][0], []
                )  # getting the first start char nb of the first tuple
                features_for_char.append((feature_name, prob))
                char_id_feature[mapping.spans[0][0]] = sorted(
                    features_for_char, key=lambda x: x[1], reverse=True
                )  # order the labels by the mse

        annotated_code = self.code
        # Annotate the code
        for characted_index, labels in sorted(char_id_feature.items(), reverse=True):
            labels = [label[0] for label in labels]  # removing the mse
            if len(labels) == len(
                self.feature_map
            ):  # all features have been detected for the modifications of this mutant, skipping
                continue
            selected_features = labels[0]  #
            annotated_code = (
                annotated_code[:characted_index]
                + comment_character
                + selected_features
                + "\n"
                + annotated_code[characted_index:]
            )
        return annotated_code

    def get_cimappings(self, feature: str) -> list[tuple[CodeImageMapping, float]]:
        """Gets a CodeImageMapping(parts of the code and the associated part of the image)
        from a string, i.e. given a string, computes which feature_names are the most similar,
        and return a list of the most probable CodeImageMapping

        Args:
            feature (str): Any string

        Returns:
            list[tuple[CodeImageMapping, float]]: Most probable part of the code/Image that the feature is in
        """
        asked_feature_embedding = self.embedding_model.encode(feature)
        similarities = self.embedding_model.similarity(
            self.key_embeddings, asked_feature_embedding
        )

        all_possible_mappings: list[tuple[CodeImageMapping, float]] = []
        for (feature_name, prob_mappings), similarity in zip(
            self.feature_map.items(), similarities
        ):

            for mapping, prob in prob_mappings:
                all_possible_mappings.append((mapping, prob * similarity))

        return sorted(all_possible_mappings, key=lambda x: x[1], reverse=True)[:2]
