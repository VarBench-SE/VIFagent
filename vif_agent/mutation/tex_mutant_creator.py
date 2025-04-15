from PIL import Image
from loguru import logger
from vif_agent.mutation.mutant import TexMutant
from vif_agent.renderer.tex_renderer import TexRenderer, TexRendererException
import re


class TexMutantCreator:
    def __init__(self):
        self.renderer = TexRenderer()

    def create_mutants(self, code: str) -> list[TexMutant]:
        """creates mutants based on a latex code

        Args:
            code (str): input latex code

        Returns:
            list[tuple[str, Image.Image, int, int]]: list of created mutants, with the image generated from it, the start of the match where the mutant has been deleted and the length of the deleted sequence.
        """
        pass


class TexMappingMutantCreator(TexMutantCreator):

    def __init__(self):

        self.definitions = [
            r"\\coordinate(?:[\[[a-zA-Z0-9]+\])?\s\(([a-zA-Z0-9]+)\)",
            r"\\node(?:[\[[a-zA-Z0-9]+\])?\s\(([[a-zA-Z0-9]+)\)",
        ]
        self.commands = [
            r"\\fill",
            r"\\draw",
            r"\\filldraw",
            r"\\shade",
            r"\\shadedraw",
        ]

        super().__init__()

    def create_mutants(self, code) -> list[TexMutant]:
        code = "\n".join(line.strip() for line in code.split("\n"))
        original_image = self.renderer.from_string_to_image(code)

        all_possible_mutants: list[list[tuple[int, int]]] = []

        # get definitions
        ex_definitions: list[re.Match] = []
        for definition in self.definitions:
            ex_definitions += list(re.finditer(definition, code))

        # get all commands
        ex_commands: list[re.Match] = []
        for command in self.commands:
            ex_commands += list(re.finditer(command, code))

        # find commands using definitions
        for match in ex_definitions:
            cur_defined_variable: str = match.group(1)
            commands_using_variable: list[re.Match] = []
            for command in ex_commands:
                after_command_str = code[command.start() :]
                full_command = code[
                    command.start() : command.start() + after_command_str.find(";")
                ]
                cur_coordinates = [
                    r.split(".")[0] for r in re.findall(r"\((.*?)\)", full_command)
                ]
                if cur_defined_variable in cur_coordinates:
                    commands_using_variable.append(command)
            all_possible_mutants.append(
                [(v.span()) for v in [match] + commands_using_variable]
            )

        # find standalone commands
        for command in ex_commands:
            after_command_str = code[command.start() :]
            all_possible_mutants.append(
                [(command.start(), command.start() + after_command_str.find(";"))]
            )

        # Find scopes
        all_possible_mutants += self._find_scopes(code)

        # find valid mutants among all of them
        valid_mutants: list[TexMutant] = []

        for mutant in all_possible_mutants:
            possible_code_mutant, char_mutant = TexMappingMutantCreator._create_mutant(
                mutant, code
            )
            try:
                image = self.renderer.from_string_to_image(possible_code_mutant)
                if (
                    image.width != original_image.width
                    or image.height != original_image.height
                ):
                    # if the new image has a different size the mutant gets ignored for now
                    continue
                valid_mutants.append(
                    TexMutant(char_mutant, possible_code_mutant, image, code, mutant)
                )
            except TexRendererException as e:
                logger.info("non valid mutant, skipping")
                continue

        valid_mutants = valid_mutants + self._find_remaining_mutants(
            valid_mutants, code, original_image
        )
        return valid_mutants

    #Probaly optimizable, but not a bottleneck
    def _find_scopes(self, code: str) -> list[list[tuple[int, int]]]:

        possible_scope_mutant: list[list[tuple[int, int]]] = []

        scope_stack = []
        index_scoped = code.find(r"\scoped{")
        index_scope = code.find(r"\begin{scope}")
        if index_scope == -1 and index_scoped == -1:
            return []
        i = min(index_scope, index_scoped)

        while i < len(code):
            current_code = code[i:]
            if current_code.startswith(r"\scoped{"):
                scope_stack.append(("scoped", i))
                i += 8
                continue
            if current_code.startswith(r"\begin{scope}"):
                scope_stack.append(("begin_scope", i))
                i += 13
                continue
            if current_code.startswith("{"):
                scope_stack.append(("ignored", i))
                i += 1
                continue
            if len(scope_stack) > 0:
                if current_code.startswith(r"}"):
                    entering_scope = scope_stack.pop()
                    i += 1
                    if entering_scope[0] != "ignored":
                        possible_scope_mutant.append([(entering_scope[1], i)])
                    continue
                if current_code.startswith(r"\end{scope}"):
                    entering_scope = scope_stack.pop()
                    i += 11
                    possible_scope_mutant.append([(entering_scope[1], i)])
                    continue
            i += 1
        return possible_scope_mutant

    def _find_remaining_mutants(
        self,
        current_valid_mutants: list[TexMutant],
        code: str,
        original_image: Image.Image,
    ):
        """uses a more basic tikz mutant search to find possible remaining mutants

        Args:
            current_valid_mutant (list[Mutant]): already found mutants
            code (str): original code

        Returns:
            list[Mutant]: list of new mutants not considered originally
        """
        # finding all commands
        all_command_spans: list[tuple[int, int]] = []
        for m in re.finditer(";", code):
            end = m.start()
            start = code.rfind("\n\\", 0, end)
            if "clip" in code[start : (start + 6)]:
                continue  # skip clip statement
            all_command_spans.append((start + 1, end))

        # removing the ones already pointed to in the current valid mutnats
        covered_char_nb = [mutant.char_mutant for mutant in current_valid_mutants]
        all_command_mutants = [
            TexMutant(span[0], (code[: span[0]] + code[span[1] :]), None, code, [span])
            for span in all_command_spans
            if span[0] not in covered_char_nb and span[0] != -1
        ]

        command_valid_mutants = []
        for cmd_mutant in all_command_mutants:
            try:
                image = self.renderer.from_string_to_image(cmd_mutant.code)
                if (
                    image.width != original_image.width
                    or image.height != original_image.height
                ):
                    # if the new image has a different size the mutant gets ignored for now
                    continue

                cmd_mutant.image = image
                command_valid_mutants.append(cmd_mutant)
            except TexRendererException as e:
                logger.info("non valid mutant, skipping")
                continue
        return command_valid_mutants

    @staticmethod
    def _create_mutant(possible_mutant: list[tuple[int, int]], code: str) -> str:
        sorted_spans = sorted(possible_mutant, key=lambda x: x[0], reverse=True)
        for start, end in sorted_spans:
            code = code[:start] + code[end:]
        return code, sorted_spans[0][0]


class TexRegMutantCreator(TexMutantCreator):
    """Regex-based latex mutant creator"""

    def __init__(self):
        super().__init__()

    def create_mutants(self, code: str) -> list[TexMutant]:
        mutants: list[TexMutant] = []
        code = "\n".join(line.strip() for line in code.split("\n"))
        original_image = self.renderer.from_string_to_image(code)
        for m in re.finditer(";", code):
            end = m.start()
            start = code.rfind("\n\\", 0, end)
            if "clip" in code[start : (start + 6)]:
                continue  # skip clip statement
            start = start + 1
            if start != -1:
                try:
                    current_possible_mutant = code[:start] + code[m.end() :]
                    image = self.renderer.from_string_to_image(current_possible_mutant)
                    if (
                        image.width != original_image.width
                        or image.height != original_image.height
                    ):
                        # if the new image has a different size the mutant gets ignored for now
                        continue
                    mutants.append(
                        TexMutant(
                            start, current_possible_mutant, image, code, [(start, end)]
                        )
                    )
                except TexRendererException as e:
                    logger.info("non valid mutant, skipping")
                    continue

        return mutants


class TexRegBrutalMutantCreator(TexRegMutantCreator):
    """Regex-based latex mutant creator"""

    def __init__(self, max_mutants: int = 1000):
        """
        Args:
            max_mutants (int): maximum number of mutants generated
        """

        self.max_mutants = max_mutants
        super().__init__()

    def create_mutants(self, code: str) -> list[tuple[str, Image.Image, int, int]]:
        """creates mutants based on a latex code

        Args:
            code (str): input latex code

        Returns:
            list[tuple[str, Image.Image, int, int]]: list of created mutants, with the image generated from it, the start of the match where the mutant has been deleted and the length of the deleted sequence.
        """
        valid_mutants = []
        code = "\n".join(line.strip() for line in code.split("\n"))
        original_image = self.renderer.from_string_to_image(code)
        all_possible_mutants: dict[int, list[tuple[str, int, int]]] = {}
        for m in re.finditer(";", code):
            end = m.start()
            for start in re.finditer(r"\n\\", code[0:end]):
                start = start.start()
                if "clip" in code[start : (start + 6)]:
                    continue  # skip clip statement
                start = start + 1
                mutants_for_feature = all_possible_mutants.get(start, [])
                mutants_for_feature.append(
                    (code[:start] + code[m.end() :], start, (m.end() - start))
                )
                all_possible_mutants[start] = mutants_for_feature
        max_mutants_per_feature = int(self.max_mutants / len(all_possible_mutants))
        for char_nb, mutants in all_possible_mutants.items():
            for mutant in mutants[:max_mutants_per_feature]:
                try:

                    image = self.renderer.from_string_to_image(mutant[0])
                    if (
                        image.width != original_image.width
                        or image.height != original_image.height
                    ):
                        # if the new image has a different size the mutant gets ignored for now
                        continue
                    valid_mutants.append(
                        TexMutant(
                            mutant[1],
                            mutant[0],
                            image,
                            code,
                            [(mutant[1], mutant[1] + mutant[2])],
                        )
                    )

                    valid_mutants.append((mutant[0], image, mutant[1], mutant[2]))
                except TexRendererException as e:
                    logger.info("non valid mutant, skipping")
                    continue

        return valid_mutants
