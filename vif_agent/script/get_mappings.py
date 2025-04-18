import argparse
import pickle
import json
import sys
import torch

from vif_agent.feature import MappedCode


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, "__dataclass_fields__"):
            return obj.__dict__
        if isinstance(obj, torch.Tensor):
            return obj.tolist()
        return super().default(obj)


parser = argparse.ArgumentParser(
    prog="get mapping script",
    description="Load a pickle file specified and gets the spans of the feature",
    epilog="Text at the bottom of help",
)

parser.add_argument("mappingfile")
parser.add_argument("-f", "--feature", nargs='+')



args = parser.parse_args()
with open(args.mappingfile, "rb") as mp:
    mapped_code: MappedCode = pickle.load(mp)

feature = " ".join(args.feature)
mappings = mapped_code.get_cimappings(feature)

print(json.dumps(mappings, cls=MyEncoder))

sys.exit(0)
