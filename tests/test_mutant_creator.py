from vif_agent.mutation.tex_mutant_creator import TexMappingMutantCreator


def test_mutant_creator():
    chimpanzee = open("tests/resources/chimpanzee.tex").read()

    mutant_creator = TexMappingMutantCreator()
    
    mutants = mutant_creator._find_scopes(chimpanzee)
    


def main():
    test_mutant_creator()


if __name__ == "__main__":
    main()
