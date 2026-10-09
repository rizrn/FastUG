import json
import logging
from classes import Command
from pathlib import Path

PARENT_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = Path(__file__).resolve().parent / "Configs/template.json"
REGEX = Command.build_standard_regex("section", 2)

logging.basicConfig(level=logging.INFO, filename="load_template_script.log")

def convert_filename_to_result_filename(filename):
    path = Path(filename)
    return str(path.with_name(path.stem + "_res" + path.suffix))

TEMPLATE_FILE = convert_filename_to_result_filename("template.md")

def load_template():
    data = {}
    logger = logging.getLogger(__name__)
    filename = TEMPLATE_FILE

    with open(PARENT_DIR / filename, "r", encoding="utf-8") as f:
        text = f.read()

    matches = REGEX.findall(text)

    for template_name, template_content in matches:
        if template_name in data:
            logger.warning(f"Duplicate template name '{template_name}' found. Skipping this entry.")
        else:
            logger.info(f"Adding template '{template_name}' to the JSON file.")
            data[template_name] = template_content.strip()

    with open(TEMPLATE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
