import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import script.script as script
import settings
from classes import Command


class LoadExistingConfigsTests(unittest.TestCase):
    def test_load_commands_builds_one_command_per_definition(self):
        commands = script.init_commands()
        definitions = script.load_json("commands.json")
        self.assertEqual(len(commands), len(definitions))
        for command in commands:
            self.assertIsInstance(command, Command)

    def test_icon_command_from_real_configs_substitutes_donation(self):
        commands = script.init_commands()
        icon_command = next(
            c for c in commands if c.regex.pattern.startswith('\\\\"icon:')
        )
        result = icon_command.substitute('\\"icon:Donation"\\')
        self.assertIn("Donation.png", result)


class CreateNewConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.config_dir = Path(self._tmpdir.name)
        self.patcher = patch.object(settings, "CONFIG_DIR", self.config_dir)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def _write_json(self, filename, data):
        with open(self.config_dir / filename, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_new_command_definition_is_loaded_and_works(self):
        self._write_json(
            "commands.json",
            {
                "highlight": {
                    "fields": ["color"],
                    "prefix": "highlight",
                    "lookup": "highlight.json",
                    "format": '<span style="background:{color}">{0}</span>',
                }
            },
        )
        self._write_json("highlight.json", {"Warning": ["yellow"]})

        commands = script.init_commands()

        self.assertEqual(len(commands), 1)
        result = commands[0].substitute('\\"highlight:Warning"\\')
        self.assertEqual(result, '<span style="background:yellow">Warning</span>')

    def test_new_lookup_entry_added_to_existing_config_is_picked_up(self):
        self._write_json(
            "commands.json",
            {
                "icon": {
                    "fields": ["file"],
                    "prefix": "icon",
                    "lookup": "icons.json",
                    "format": '<img src="Icons/{file}" />',
                }
            },
        )
        self._write_json("icons.json", {"Ticket": ["Ticket Icon.png"]})

        commands = script.init_commands()
        result = commands[0].substitute('\\"icon:Ticket"\\')

        self.assertEqual(result, '<img src="Icons/Ticket Icon.png" />')

    def test_multiple_new_command_definitions_all_load_independently(self):
        self._write_json(
            "commands.json",
            {
                "icon": {
                    "fields": ["file"],
                    "prefix": "icon",
                    "lookup": "icons.json",
                    "format": '<img src="Icons/{file}" />',
                },
                "highlight": {
                    "fields": ["color"],
                    "prefix": "highlight",
                    "lookup": "highlight.json",
                    "format": '<span style="background:{color}">{0}</span>',
                },
            },
        )
        self._write_json("icons.json", {"Donation": ["Donation Section.png"]})
        self._write_json("highlight.json", {"Warning": ["yellow"]})

        commands = script.init_commands()

        self.assertEqual(len(commands), 2)
        prefixes = {c.regex.pattern for c in commands}
        self.assertTrue(any("icon:" in p for p in prefixes))
        self.assertTrue(any("highlight:" in p for p in prefixes))

    def test_load_json_reads_freshly_created_config_file(self):
        self._write_json("new_lookup.json", {"Key": ["value"]})
        self.assertEqual(script.load_json("new_lookup.json"), {"Key": ["value"]})


if __name__ == "__main__":
    unittest.main()
