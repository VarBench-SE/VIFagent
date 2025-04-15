import pickle

from vif_agent.feature import MappedCode

with open("tests/resources/mapped_chimp_code.pickle", "rb") as mp:
        mapped_code:MappedCode = pickle.load(mp)
        
mappings = mapped_code.get_cimappings("ears")

print(mapped_code.feature_map.keys())

new_code = mapped_code.code
for mapping in sorted(mappings,key=lambda x: x[0].spans[0],reverse=True):#does not work with multispan codeMappings
    for span in mapping[0].spans:
        
        new_code= new_code[:span[1]]+r"%>"+"\n"+new_code[span[1]:]
        new_code= new_code[:span[0]]+r"%<"+"\n"+new_code[span[0]:]
        
        
with open("identified.tex", "w") as md_chimp:
   md_chimp.write(new_code)