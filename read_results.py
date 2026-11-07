import json
try:
    with open("/data/workspace/results.json", "r") as f:
        print(f.read())
except Exception as e:
    print(e)
