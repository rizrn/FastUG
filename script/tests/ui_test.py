import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classes import Command

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = REPO_ROOT / "script" / "Configs"
STYLESHEETS = [REPO_ROOT / "styles.css", REPO_ROOT / ".crossnote" / "style.less"]
SOURCES = [REPO_ROOT / name for name in ("userguide.md", "template.md", "commands.md")]

SVG_CLASS_DEF_RE = re.compile(r'\.svg-([\w-]+)\s*\{\s*--svg:\s*(url\("[^"]+"\))')
UISVG_CALL_RE = Command.build_standard_regex("uisvg", 3)
UIICON_CALL_RE = Command.build_standard_regex("uiicon", 2)
SVG_COLOR_DEF_RE = re.compile(r'\.svg-([\w-]+)\s*\{[^}]*?--svg-color:\s*([^;]+);')


def load_json(filename):
    with open(CONFIG_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


def build_command(name):
    definition = load_json("commands.json")[name]
    regex = Command.build_standard_regex(definition["prefix"], len(definition["fields"]))
    return Command(name, regex, definition["format"], load_json(definition["lookup"]), definition["fields"])


def svg_definitions(stylesheet):
    return dict(SVG_CLASS_DEF_RE.findall(stylesheet.read_text(encoding="utf-8")))


class UiCommandTests(unittest.TestCase):
    def setUp(self):
        self.ui = build_command("ui")
        self.uisvg = build_command("uisvg")
        self.uiicon = build_command("uiicon")

    def test_ui_expands_to_text_only_element(self):
        self.assertEqual(
            self.ui.substitute('Click \\"ui:primary:Save"\\ now.'),
            'Click <span class="ui ui-primary"><span class="ui-label">Save</span></span> now.',
        )

    def test_uisvg_expands_to_icon_and_text_element(self):
        self.assertEqual(
            self.uisvg.substitute('Click \\"uisvg:primary:refresh:Refresh"\\ now.'),
            'Click <span class="ui ui-primary"><span class="ui-label">'
            '<i class="ui-svg svg-refresh"></i>Refresh</span></span> now.',
        )

    def test_uiicon_expands_to_icon_only_element(self):
        self.assertEqual(
            self.uiicon.substitute('Click \\"uiicon:primary:more-options"\\ now.'),
            'Click <span class="ui ui-primary ui-icon-only"><span class="ui-label">'
            '<i class="ui-svg svg-more-options"></i></span></span> now.',
        )

    def test_icon_sits_inside_the_label_so_the_label_is_the_only_flex_item(self):
        result = self.uisvg.substitute('\\"uisvg:primary:refresh:Refresh"\\')
        inner = result[len('<span class="ui ui-primary">'):-len("</span>")]
        self.assertTrue(inner.startswith('<span class="ui-label">'))
        self.assertTrue(inner.endswith("</span>"))
        self.assertEqual(inner.count('<span class="ui-label">'), 1)

    def test_ui_does_not_match_a_uisvg_call(self):
        text = '\\"uisvg:primary:refresh:Refresh"\\'
        self.assertEqual(self.ui.substitute(text), text)

    def test_unknown_style_is_reported_not_expanded(self):
        self.assertEqual(
            self.ui.substitute('\\"ui:nonexistent:Save"\\'),
            "Error: File 'nonexistent' not found for command 'ui'.",
        )

    def test_expanded_output_is_safe_to_nest(self):
        for style in load_json("ui.json"):
            for result in (
                self.ui.substitute(f'\\"ui:{style}:Label"\\'),
                self.uisvg.substitute(f'\\"uisvg:{style}:refresh:Label"\\'),
                self.uiicon.substitute(f'\\"uiicon:{style}:refresh"\\'),
            ):
                self.assertNotIn(":", result)
                self.assertNotIn('"\\', result)
                self.assertNotIn("\n", result)

    def test_ui_commands_run_before_box(self):
        order = list(load_json("commands.json"))
        self.assertLess(order.index("ui"), order.index("box"))
        self.assertLess(order.index("uisvg"), order.index("box"))
        self.assertLess(order.index("uiicon"), order.index("box"))

    def test_uisvg_survives_inside_box_content(self):
        box = build_command("box")
        text = '\\"box:tip:Heads up:Click \\"uisvg:primary:refresh:Refresh"\\ first."\\'
        text = box.substitute(self.uisvg.substitute(text))
        self.assertIn('<i class="ui-svg svg-refresh"></i>', text)
        self.assertIn("first.", text)
        self.assertNotIn('"\\', text)


class UiStylesheetTests(unittest.TestCase):
    def test_every_ui_style_is_styled_in_both_stylesheets(self):
        for stylesheet in STYLESHEETS:
            css = stylesheet.read_text(encoding="utf-8")
            for style in load_json("ui.json"):
                self.assertRegex(css, r"\.ui-" + re.escape(style) + r"\s*\{", f"{stylesheet.name}: .ui-{style}")

    def test_both_stylesheets_define_the_same_icons(self):
        css, less = (svg_definitions(s) for s in STYLESHEETS)
        self.assertTrue(css, "no svg-{name} rules found in styles.css")
        self.assertEqual(css, less)

    def test_both_stylesheets_give_icons_the_same_colour(self):
        css, less = (dict(SVG_COLOR_DEF_RE.findall(s.read_text(encoding="utf-8"))) for s in STYLESHEETS)
        self.assertEqual(css, less)

    def test_icon_only_element_drops_the_icon_to_text_gap(self):
        for stylesheet in STYLESHEETS:
            css = stylesheet.read_text(encoding="utf-8")
            match = re.search(r"\.ui-icon-only \.ui-svg\s*\{[^}]*margin-right:\s*0;", css)
            self.assertIsNotNone(match, stylesheet.name)
            self.assertLess(css.index(".ui-sidemenu-category .ui-svg"), match.start(), stylesheet.name)

    def test_icon_colour_is_only_used_by_the_sidemenu_category(self):
        for stylesheet in STYLESHEETS:
            css = stylesheet.read_text(encoding="utf-8")
            users = re.findall(r'([^{}]+)\{[^}]*var\(--svg-color', css)
            self.assertEqual([" ".join(u.split()) for u in users], [".ui-sidemenu-category .ui-svg"], stylesheet.name)

    def test_every_icon_used_in_the_sources_is_defined(self):
        defined = svg_definitions(STYLESHEETS[0])
        for source in SOURCES:
            if not source.exists():
                continue
            text = source.read_text(encoding="utf-8")
            calls = [(svg, label) for _, svg, label in UISVG_CALL_RE.findall(text)]
            calls += [(svg, "icon only") for _, svg in UIICON_CALL_RE.findall(text)]
            for svg, label in calls:
                self.assertIn(svg.strip(), defined, f"{source.name}: svg-{svg.strip()} ({label.strip()})")


if __name__ == "__main__":
    unittest.main()
