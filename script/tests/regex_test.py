import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classes import Command, CustomCommand


class BuildRegexTests(unittest.TestCase):
    def test_single_field_pattern(self):
        regex = Command.build_standard_regex("icon", 1)
        self.assertEqual(regex.pattern, '\\\\"icon:(.+?)"\\\\')

    def test_multi_field_pattern_uses_colon_restricted_groups_except_last(self):
        regex = Command.build_standard_regex("box", 3)
        self.assertEqual(
            regex.pattern,
            '\\\\"box:([^:]+):([^:]+):(.+?)"\\\\',
        )

    def test_escaped_fields_are_opt_in_via_allow_escaped_fields(self):
        regex = Command.build_standard_regex("box", 3, allow_escaped_fields=True)
        self.assertEqual(
            regex.pattern,
            '\\\\"box:((?:\\s*\\$\\(.*?\\)\\$\\s*|[^:]+)):((?:\\s*\\$\\(.*?\\)\\$\\s*|[^:]+)):(.+?)"\\\\',
        )

    def test_single_field_match_extracts_phrase(self):
        regex = Command.build_standard_regex("icon", 1)
        text = 'See \\"icon:Donation"\\ for details.'
        match = regex.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "Donation")

    def test_multi_field_match_extracts_each_field(self):
        regex = Command.build_standard_regex("box", 3)
        text = 'Note: \\"box:tip:Title Here:Body text"\\ end'
        match = regex.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.groups(), ("tip", "Title Here", "Body text"))

    def test_plain_quotes_without_backslash_do_not_match(self):
        regex = Command.build_standard_regex("icon", 1)
        text = '"icon:Donation"'
        self.assertIsNone(regex.search(text))

    def test_wrong_prefix_does_not_match(self):
        regex = Command.build_standard_regex("icon", 1)
        text = '\\"diagram:Donation"\\'
        self.assertIsNone(regex.search(text))

    def test_non_final_field_cannot_contain_colon(self):
        regex = Command.build_standard_regex("box", 3)
        text = '\\"box:tip:Title:With:Extra:Colons"\\'
        match = regex.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.groups(), ("tip", "Title", "With:Extra:Colons"))

    def test_final_field_spans_multiple_lines(self):
        regex = Command.build_standard_regex("box", 3)
        text = '\\"box:tip:Title:line one\nline two"\\'
        match = regex.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(3), "line one\nline two")

    def test_unterminated_command_does_not_match(self):
        regex = Command.build_standard_regex("icon", 1)
        text = '\\"icon:Donation'
        self.assertIsNone(regex.search(text))

    def test_command_closed_with_bare_quote_no_longer_matches(self):
        regex = Command.build_standard_regex("icon", 1)
        text = 'See \\"icon:Donation" for details.'
        self.assertIsNone(regex.search(text))

    def test_findall_matches_multiple_occurrences(self):
        regex = Command.build_standard_regex("icon", 1)
        text = '\\"icon:Donation"\\ and \\"icon:Ticket"\\'
        self.assertEqual(regex.findall(text), ["Donation", "Ticket"])

    def test_final_field_can_contain_unrelated_quoted_phrases(self):
        regex = Command.build_standard_regex("box", 3)
        text = '\\"box:tip:Title:click "Filter" then "Search""\\'
        match = regex.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(
            match.groups(), ("tip", "Title", 'click "Filter" then "Search"')
        )

    def test_non_final_field_can_contain_quotes(self):
        regex = Command.build_standard_regex("box", 3)
        text = '\\"box:tip:<div class="title">Title</div>:Body text"\\'
        match = regex.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(
            match.groups(), ("tip", '<div class="title">Title</div>', "Body text")
        )

    def test_custom_command_non_final_field_wrapped_in_dollar_parens_can_contain_colons(self):
        custom = CustomCommand("Overview", ["a", "b", "c"], "{a} {b} {c}")
        text = '\\"custom:Overview:$(nested:with:colons)$:middle:last"\\'
        match = custom.regex.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(
            match.groups(), ("$(nested:with:colons)$", "middle", "last")
        )


class SubstituteTests(unittest.TestCase):
    def setUp(self):
        self.fmt = '<img src="Icons/{file}" alt="{0}" />'
        self.lookup = {"Donation": "Donation Section.png"}
        self.regex = Command.build_standard_regex("icon", 1)
        self.command = Command("test", self.regex, self.fmt, self.lookup, ["file"])

    def test_known_key_is_expanded_using_lookup(self):
        text = 'A \\"icon:Donation"\\ B'
        result = self.command.substitute(text)
        self.assertEqual(
            result, 'A <img src="Icons/Donation Section.png" alt="Donation" /> B'
        )

    def test_unmatched_text_is_left_untouched(self):
        text = "No shorthand here."
        self.assertEqual(self.command.substitute(text), text)

    def test_multiple_occurrences_all_expanded(self):
        text = '\\"icon:Donation"\\ and \\"icon:Donation"\\ again'
        result = self.command.substitute(text)
        self.assertEqual(result.count("Donation Section.png"), 2)

    def test_unknown_key_raises_keyerror_on_current_implementation(self):
        text = '\\"icon:Missing"\\'
        self.assertEqual(self.command.substitute(text), "Error: File 'Missing' not found for command 'test'.")

    def test_list_lookup_value_zips_across_all_fields(self):
        fmt = '<div class="{type}-box">{title}</div>'
        lookup = {"tip": ["tip", "Tip"]}
        regex = Command.build_standard_regex("box", 2)
        command = Command("test", regex, fmt, lookup, ["type", "title"])
        text = 'A \\"box:tip:ignored"\\ B'
        result = command.substitute(text)
        self.assertEqual(result, 'A <div class="tip-box">Tip</div> B')


class CustomCommandEscapingTests(unittest.TestCase):
    def test_escaped_field_value_is_unwrapped_during_substitute(self):
        custom = CustomCommand("Overview", ["a", "b"], "{a} | {b}")
        text = '\\"custom:Overview:$(nested:with:colons)$:last"\\'
        result = custom.substitute(text)
        self.assertEqual(result, "nested:with:colons | last")

    def test_unescaped_field_value_is_left_as_is(self):
        custom = CustomCommand("Overview", ["a", "b"], "{a} | {b}")
        text = '\\"custom:Overview:plain:last"\\'
        result = custom.substitute(text)
        self.assertEqual(result, "plain | last")

    def test_escaped_field_on_its_own_line_after_the_call_still_unwraps(self):
        icon_fmt = '<img src="Icons/{file}" />'
        icon_regex = Command.build_standard_regex("icon", 1)
        icon_command = Command("test", icon_regex, icon_fmt, {"Event": "Event.png"}, ["file"])

        custom = CustomCommand("Overview", ["intro", "last"], "{intro} | {last}")

        text = 'Note: \\"custom:Overview:\n$(Click \\"icon:Event"\\)$\n:last"\\ end'

        text = icon_command.substitute(text)
        text = custom.substitute(text)

        self.assertEqual(text, 'Note: Click <img src="Icons/Event.png" /> | last end')

    def test_escaped_non_final_field_can_hold_a_nested_leaf_command(self):
        icon_fmt = '<img src="Icons/{file}" />'
        icon_regex = Command.build_standard_regex("icon", 1)
        icon_command = Command("test", icon_regex, icon_fmt, {"Search": "Search.png"}, ["file"])

        custom = CustomCommand("Overview", ["type", "title", "content"], '<div class="{type}-box">{title}: {content}</div>')

        text = 'Note: \\"custom:Overview:tip:$(Click \\"icon:Search"\\)$:Body text"\\ end'

        text = icon_command.substitute(text)
        text = custom.substitute(text)

        self.assertEqual(
            text,
            'Note: <div class="tip-box">Click <img src="Icons/Search.png" />: Body text</div> end',
        )


class NestingTests(unittest.TestCase):
    def test_leaf_command_output_survives_inside_box_content(self):
        icon_fmt = '<img src="Icons/{file}" />'
        icon_regex = Command.build_standard_regex("icon", 1)
        icon_command = Command("test", icon_regex, icon_fmt, {"Donation": "Donation Section.png"}, ["file"])

        box_fmt = '<div class="{type}-box">{title}: {content}</div>'
        box_regex = Command.build_standard_regex("box", 3)
        box_command = Command("test", box_regex, box_fmt, {"tip": "tip"}, ["type", "title", "content"])

        text = 'Note: \\"box:tip:Heads up:See \\"icon:Donation"\\ for details."\\ end'

        text = icon_command.substitute(text)
        text = box_command.substitute(text)

        self.assertEqual(
            text,
            'Note: <div class="tip-box">Heads up: See <img src="Icons/Donation Section.png" /> for details.</div> end',
        )


class MultilineTests(unittest.TestCase):
    def test_flags_include_multiline_and_dotall(self):
        regex = Command.build_standard_regex("icon", 1)
        self.assertTrue(regex.flags & re.MULTILINE)
        self.assertTrue(regex.flags & re.DOTALL)

    def test_shorthand_found_among_surrounding_lines(self):
        regex = Command.build_standard_regex("icon", 1)
        text = "line one\nline two\n\\\"icon:Donation\"\\\nline four\nline five"
        match = regex.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "Donation")

    def test_non_final_field_can_contain_embedded_newline(self):
        regex = Command.build_standard_regex("box", 3)
        text = '\\"box:ti\np:Title\nHere:Body\ntext"\\'
        match = regex.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.groups(), ("ti\np", "Title\nHere", "Body\ntext"))

    def test_final_field_with_blank_lines(self):
        regex = Command.build_standard_regex("box", 3)
        text = '\\"box:tip:Title:para one\n\npara two"\\'
        match = regex.search(text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(3), "para one\n\npara two")

    def test_findall_across_separate_lines(self):
        regex = Command.build_standard_regex("icon", 1)
        text = '\\"icon:Donation"\\\nsome text\n\\"icon:Ticket"\\\nmore text'
        self.assertEqual(regex.findall(text), ["Donation", "Ticket"])

    def test_substitute_replaces_shorthand_within_multiline_document(self):
        fmt = '<img src="Icons/{file}" alt="{0}" />'
        lookup = {"Donation": "Donation Section.png"}
        regex = Command.build_standard_regex("icon", 1)
        command = Command("test", regex, fmt, lookup, ["file"])

        text = "Intro paragraph.\n\nSee \\\"icon:Donation\"\\ below.\n\nOutro paragraph."
        result = command.substitute(text)

        self.assertEqual(
            result,
            'Intro paragraph.\n\nSee <img src="Icons/Donation Section.png" '
            'alt="Donation" /> below.\n\nOutro paragraph.',
        )


if __name__ == "__main__":
    unittest.main()
