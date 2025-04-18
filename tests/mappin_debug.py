import pickle
import json

from numpy import float32
import torch
from vif_agent.feature import MappedCode

with open("mapped_chimp_code.pickle", "rb") as mp:
        mapped_code:MappedCode = pickle.load(mp)
        
class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, '__dataclass_fields__'):
            return obj.__dict__
        if isinstance(obj, torch.Tensor):
            return obj.tolist()
        if isinstance(obj, float32):
            return float(obj)
        return super().default(obj)

for m in mapped_code.feature_map.items():
        print(m[0])
        for s in m[1][:3]:
                print(s[0].spans)


print(json.dumps(mapped_code.feature_map,indent=4,cls=MyEncoder))