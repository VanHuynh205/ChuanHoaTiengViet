"""Extract the official OpenAPI document from the downloaded reference page."""
import json
from html.parser import HTMLParser
from pathlib import Path


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_script = False
        self.values = []

    def handle_starttag(self, tag, attrs):
        self.in_script = tag == "script"

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_script = False

    def handle_data(self, data):
        if self.in_script:
            try:
                self.values.append(json.loads(data))
            except ValueError:
                pass


parser = Scripts()
parser.feed(Path(__file__).with_name("kimi-infer.html").read_text(encoding="utf-8"))
for value in parser.values:
    if not isinstance(value, dict) or "document" not in value:
        continue
    schema = value["document"]["api"]["schema"]
    for name, model in schema["components"]["schemas"].items():
        if "properties" in model and "messages" in model["properties"]:
            print(json.dumps({"name": name, "request_properties": model["properties"]}, ensure_ascii=True))
    for path, operations in schema["paths"].items():
        print(json.dumps({"path": path, "parameters": {method: spec.get("parameters", []) for method, spec in operations.items()}}, ensure_ascii=True))
