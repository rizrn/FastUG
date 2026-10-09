import json
from pathlib import Path
import os
import logging
import re

JSON_DIR = Path(__file__).parent / "Configs"
DIAGRAMS_DIR = Path(__file__).parent.parent / "Diagrams"
ICONS_DIR = Path(__file__).parent.parent / "Icons"

dirs = [DIAGRAMS_DIR, ICONS_DIR]

def split_camel_case(text):
    return re.sub(r'(?<!^)(?=[A-Z][a-z])|(?<=[a-z0-9])(?=[A-Z])', ' ', text)

def populate_json(input_dir, output_dir, output_filename):
    data = {}
    for file in os.listdir(input_dir):
        if file.endswith(".png"):
            diagram_filename = file[:-4]
            diagram_name = split_camel_case(diagram_filename)

            data[diagram_name] = diagram_filename + ".png"

    with open(output_dir / output_filename, 'w') as json_file:
        json.dump(data, json_file, indent=4)

def load_pictures():
    for dir in dirs:
        if dir == DIAGRAMS_DIR:
            output_filename = "diagrams.json"
        elif dir == ICONS_DIR:
            output_filename = "icons.json"
        else:
            continue

        populate_json(dir, JSON_DIR, output_filename)
        logging.info(f"Populated {output_filename} in {JSON_DIR}")
