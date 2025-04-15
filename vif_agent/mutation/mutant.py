from dataclasses import dataclass

from PIL import Image


@dataclass
class TexMutant:
    char_mutant: int
    code: str
    image: Image.Image
    original_code: str
    deleted_spans: list[tuple[int, int]]

    def removed_char_nb(self):
        return sum([sp[1] - sp[0] for sp in self.deleted_spans])
