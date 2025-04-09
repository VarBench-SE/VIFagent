from PIL import Image
from loguru import logger
from vif_agent.renderer.tex_renderer import TexRenderer, TexRendererException
import re


class TexRegMutantCreator:
    """Regex-based latex mutant creator
    \\begin\{(\w+)\}(?:\[[^\]]*\])?(.*?)\\end\{\1\}
    """

    def __init__(self):
        self.renderer = TexRenderer()
        pass

    def create_mutants(self, code: str) -> list[tuple[str, Image.Image, int]]:
        mutants = []
        code = '\n'.join(line.strip() for line in code.split('\n'))
        original_image = self.renderer.from_string_to_image(code)        
        for m in re.finditer(";", code):
            end = m.start()
            start = code.rfind("\n\\", 0, end)
            if start != -1:
                try:
                    current_possible_mutant = code[:start]+code[m.end():]
                    image = self.renderer.from_string_to_image(current_possible_mutant)
                    if image.width != original_image.width or image.height != original_image.height:
                        #if the new image has a different size the mutant gets ignored for now
                        continue
                    mutants.append((current_possible_mutant,image,start))
                except TexRendererException as e:
                    logger.info("non valid mutant, skipping")
                    continue

        return mutants
        

