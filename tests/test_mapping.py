import pickle
import json

from numpy import float32
import torch
from vif_agent.feature import MappedCode

with open("extension/tikz-mapped/src/resources/mapped_shark_code.pickle", "rb") as mp:
        mapped_code:MappedCode = pickle.load(mp)


mappings = mapped_code.get_cimappings("teeth")


new_code = mapped_code.code
for mapping in sorted(mappings,key=lambda x: x[0].spans[0],reverse=True)[0:3]:#does not work with multispan codeMappings
    for span in mapping[0].spans:
        
        new_code= new_code[:span[1]]+r"%>"+"\n"+new_code[span[1]:]
        new_code= new_code[:span[0]]+r"%<"+"\n"+new_code[span[0]:]
        
        
with open("identified.tex", "w") as md_chimp:
   md_chimp.write(new_code)