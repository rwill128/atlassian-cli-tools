import json
import sys


def dump_json(data: object) -> None:
    json.dump(data, sys.stdout, indent=2, sort_keys=False)
    sys.stdout.write("\n")

