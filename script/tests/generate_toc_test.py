import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_toc import (
    HEADING_MIN_FONT_SIZE,
    TOC_ROWS_FIRST_PAGE,
    TOC_ROWS_PER_PAGE,
    PdfInputError,
    assign_ids,
    assign_numbers,
    build_toc_html,
    chunk_toc_entries,
    find_page_numbers,
    insert_toc,
    parse_headings,
    plan_toc_pages,
    rewrite_headings,
    slugify,
)

HEADING_SIZE = HEADING_MIN_FONT_SIZE + 3
BODY_SIZE = HEADING_MIN_FONT_SIZE - 3


class FakePage:
    def __init__(self, headings=(), body=()):
        self._headings = headings
        self._body = body

    @staticmethod
    def _block(text, size):
        lines = text if isinstance(text, list) else [text]
        return {"lines": [{"spans": [{"text": line, "size": size}]} for line in lines]}

    def get_text(self, kind):
        assert kind == "dict"
        return {"blocks": (
            [self._block(t, HEADING_SIZE) for t in self._headings]
            + [self._block(t, BODY_SIZE) for t in self._body]
        )}


class FakeDoc:
    def __init__(self, pages, is_pdf=True):
        self._pages = pages
        self.page_count = len(pages)
        self.is_pdf = is_pdf

    def __getitem__(self, index):
        return self._pages[index]

    def close(self):
        pass


def patched_pymupdf(doc):
    fake_module = types.ModuleType("pymupdf")
    fake_module.open = lambda path: doc
    return patch.dict(sys.modules, {"pymupdf": fake_module})


class SlugifyTests(unittest.TestCase):
    def test_lowercases_and_hyphenates(self):
        self.assertEqual(slugify("Quick Start", set()), "quick-start")

    def test_strips_markdown_emphasis_before_slugifying(self):
        self.assertEqual(slugify("**Bold** Title", set()), "bold-title")

    def test_collapses_punctuation_and_trims_edges(self):
        self.assertEqual(slugify(" Ad-Hoc event registration! ", set()), "ad-hoc-event-registration")

    def test_dedupes_against_already_used_slugs(self):
        used = {"change-courses"}
        self.assertEqual(slugify("Change courses", used), "change-courses-1")
        used.add("change-courses-1")
        self.assertEqual(slugify("Change courses", used), "change-courses-2")


class ParseHeadingsTests(unittest.TestCase):
    def test_finds_atx_headings_with_levels(self):
        text = "# Quick Start\n\nSome text.\n\n## Sub section\n"
        headings = parse_headings(text)
        self.assertEqual(
            [(h["level"], h["raw_text"]) for h in headings],
            [(1, "Quick Start"), (2, "Sub section")],
        )

    def test_finds_raw_html_headings_and_preserves_attrs(self):
        text = '<h2 class="no-break" id="my-id">Creating Attendance QR Code</h2>'
        headings = parse_headings(text)
        self.assertEqual(len(headings), 1)
        self.assertEqual(headings[0]["level"], 2)
        self.assertEqual(headings[0]["raw_text"], "Creating Attendance QR Code")
        self.assertIn('class="no-break"', headings[0]["attrs"])
        self.assertIn('id="my-id"', headings[0]["attrs"])

    def test_mixed_atx_and_html_headings_stay_in_document_order(self):
        text = (
            "# First\n\n"
            '<h2 class="no-break">Second (no-break)</h2>\n\n'
            "## Third\n"
        )
        headings = parse_headings(text)
        self.assertEqual(
            [h["raw_text"] for h in headings],
            ["First", "Second (no-break)", "Third"],
        )

    def test_finds_html_heading_with_an_unquoted_id(self):
        text = '<h2 class="no-break" id=filter-enquiry>Filtering Enquiry</h2>'
        headings = parse_headings(text)
        self.assertEqual(len(headings), 1)
        self.assertEqual(headings[0]["raw_text"], "Filtering Enquiry")
        self.assertIn('class="no-break"', headings[0]["attrs"])

    def test_finds_html_heading_with_a_single_quoted_id(self):
        text = "<h2 class='no-break' id='filter-enquiry'>Filtering Enquiry</h2>"
        headings = parse_headings(text)
        self.assertEqual([h["raw_text"] for h in headings], ["Filtering Enquiry"])

    def test_dropped_html_heading_would_also_misnumber_the_ones_after_it(self):
        text = (
            "# Intakes\n\n"
            "## Adding Intake\n\n"
            '<h2 class="no-break" id=filter-intake>Filtering intakes</h2>\n\n'
            "## Converting intakes to cases\n"
        )
        headings = assign_numbers(parse_headings(text))
        self.assertEqual(
            [(h["number"], h["raw_text"]) for h in headings],
            [
                ("1", "Intakes"),
                ("1.1", "Adding Intake"),
                ("1.2", "Filtering intakes"),
                ("1.3", "Converting intakes to cases"),
            ],
        )

    def test_ignores_h3_and_deeper(self):
        text = "# One\n\n### Not tracked\n"
        headings = parse_headings(text)
        self.assertEqual([h["raw_text"] for h in headings], ["One"])


class AssignIdsTests(unittest.TestCase):
    def test_assigns_slug_when_no_existing_id(self):
        headings = parse_headings("# Quick Start\n")
        assign_ids(headings)
        self.assertEqual(headings[0]["id"], "quick-start")

    def test_reuses_existing_id_instead_of_regenerating(self):
        text = '<h2 class="no-break" id="creating-attendance-qr-code">Creating Attendance QR Code</h2>'
        headings = parse_headings(text)
        assign_ids(headings)
        self.assertEqual(headings[0]["id"], "creating-attendance-qr-code")

    def test_reuses_an_unquoted_existing_id(self):
        text = '<h2 class="no-break" id=filter-enquiry>Filtering Enquiry</h2>'
        headings = parse_headings(text)
        assign_ids(headings)
        self.assertEqual(headings[0]["id"], "filter-enquiry")

    def test_does_not_mistake_a_suffixed_attribute_for_an_id(self):
        headings = parse_headings('<h2 data-id="not-the-id">Title</h2>')
        assign_ids(headings)
        self.assertEqual(headings[0]["id"], "title")

    def test_dedupes_ids_for_duplicate_heading_text(self):
        headings = parse_headings("# Change courses\n\n## Change courses\n")
        assign_ids(headings)
        self.assertEqual([h["id"] for h in headings], ["change-courses", "change-courses-1"])


class RewriteHeadingsTests(unittest.TestCase):
    def test_atx_heading_becomes_raw_html_with_id(self):
        text = "Intro\n\n# Quick Start\n\nBody text."
        headings = parse_headings(text)
        assign_ids(headings)
        result = rewrite_headings(text, headings)
        self.assertEqual(result, 'Intro\n\n<h1 id="quick-start">Quick Start</h1>\n\nBody text.')

    def test_existing_html_heading_keeps_class_and_gets_id(self):
        text = '<h2 class="no-break">Creating Attendance QR Code</h2>'
        headings = parse_headings(text)
        assign_ids(headings)
        result = rewrite_headings(text, headings)
        self.assertEqual(
            result,
            '<h2 class="no-break" id="creating-attendance-qr-code">Creating Attendance QR Code</h2>',
        )

    def test_existing_id_is_not_duplicated_on_rewrite(self):
        text = '<h2 id="my-id">Title</h2>'
        headings = parse_headings(text)
        assign_ids(headings)
        result = rewrite_headings(text, headings)
        self.assertEqual(result.count('id="my-id"'), 1)

    def test_unquoted_id_is_normalized_and_not_duplicated(self):
        text = '<h2 class="no-break" id=filter-enquiry>Filtering Enquiry</h2>'
        headings = parse_headings(text)
        assign_ids(headings)
        result = rewrite_headings(text, headings)
        self.assertEqual(
            result,
            '<h2 class="no-break" id="filter-enquiry">Filtering Enquiry</h2>',
        )

    def test_inserts_blank_line_when_heading_has_none(self):
        text = "# Quick Start\nTo log in into the system:\n1) Connect to the company VPN"
        headings = parse_headings(text)
        assign_ids(headings)
        result = rewrite_headings(text, headings)
        self.assertEqual(
            result,
            '<h1 id="quick-start">Quick Start</h1>\n\nTo log in into the system:\n1) Connect to the company VPN',
        )

    def test_existing_blank_line_is_not_duplicated(self):
        text = "# Quick Start\n\nAlready has a blank line."
        headings = parse_headings(text)
        assign_ids(headings)
        result = rewrite_headings(text, headings)
        self.assertEqual(
            result,
            '<h1 id="quick-start">Quick Start</h1>\n\nAlready has a blank line.',
        )


class AssignNumbersTests(unittest.TestCase):
    def test_h1_increments_and_h2_nests_under_it(self):
        text = "# Events\n\n## Filtering events\n\n## Editing events\n\n# Attendance\n\n## View attendance\n"
        headings = parse_headings(text)
        assign_numbers(headings)
        self.assertEqual(
            [h["number"] for h in headings],
            ["1", "1.1", "1.2", "2", "2.1"],
        )

    def test_h2_before_any_h1_still_gets_a_number(self):
        text = "## Orphan section\n\n# First real section\n"
        headings = parse_headings(text)
        assign_numbers(headings)
        self.assertEqual([h["number"] for h in headings], ["0.1", "1"])


class BuildTocHtmlTests(unittest.TestCase):
    def test_entries_are_a_flat_list_classed_by_heading_level(self):
        text = "# Events\n\n## Filtering events\n\n## Editing events\n\n# Attendance\n"
        headings = parse_headings(text)
        assign_ids(headings)
        assign_numbers(headings)
        html = build_toc_html(headings)

        self.assertEqual(html.count("<li"), 4)
        self.assertEqual(html.count("</li>"), 4)
        self.assertEqual(html.count("<ul"), 1)
        self.assertIn('<li class="toc-h1"><a href="#events">', html)
        self.assertIn('<li class="toc-h1"><a href="#attendance">', html)
        self.assertIn('<li class="toc-h2"><a href="#filtering-events">', html)

    def test_entry_includes_number_title_and_dot_leader(self):
        text = "# Quick Start\n"
        headings = parse_headings(text)
        assign_ids(headings)
        assign_numbers(headings)
        html = build_toc_html(headings)
        self.assertIn('<span class="toc-number">1</span>', html)
        self.assertIn('<span class="toc-title">Quick Start</span>', html)
        self.assertIn('<span class="toc-dots"></span>', html)

    def test_page_numbers_are_included_when_given(self):
        text = "# Quick Start\n"
        headings = parse_headings(text)
        assign_ids(headings)
        assign_numbers(headings)
        html = build_toc_html(headings, page_numbers={"quick-start": 3})
        self.assertIn('<span class="toc-page">3</span>', html)

    def test_missing_page_number_omits_the_span(self):
        text = "# Quick Start\n"
        headings = parse_headings(text)
        assign_ids(headings)
        assign_numbers(headings)
        html = build_toc_html(headings, page_numbers={})
        self.assertNotIn("toc-page", html)


class ChunkTocEntriesTests(unittest.TestCase):
    def entries(self, n):
        return [
            {"id": f"h{i}", "level": 1, "raw_text": f"Heading {i}", "number": str(i + 1)}
            for i in range(n)
        ]

    def test_short_toc_is_a_single_page(self):
        chunks = chunk_toc_entries(self.entries(TOC_ROWS_FIRST_PAGE))
        self.assertEqual([len(c) for c in chunks], [TOC_ROWS_FIRST_PAGE])
        self.assertEqual(plan_toc_pages(self.entries(TOC_ROWS_FIRST_PAGE)), 1)

    def test_overflow_starts_a_second_page_at_the_continuation_capacity(self):
        entries = self.entries(TOC_ROWS_FIRST_PAGE + TOC_ROWS_PER_PAGE + 1)
        chunks = chunk_toc_entries(entries)
        self.assertEqual(
            [len(c) for c in chunks],
            [TOC_ROWS_FIRST_PAGE, TOC_ROWS_PER_PAGE, 1],
        )
        self.assertEqual(plan_toc_pages(entries), 3)

    def test_every_entry_survives_the_split_in_order(self):
        entries = self.entries(TOC_ROWS_FIRST_PAGE + 5)
        flattened = [e for chunk in chunk_toc_entries(entries) for e in chunk]
        self.assertEqual(flattened, entries)

    def test_html_puts_an_explicit_page_break_between_chunks(self):
        entries = self.entries(TOC_ROWS_FIRST_PAGE + 1)
        html = build_toc_html(entries)
        self.assertEqual(html.count('<div class="page-break"></div>'), 1)
        self.assertEqual(html.count('<ul class="toc">'), 2)
        self.assertEqual(html.count("</ul>"), 2)
        self.assertEqual(html.count("toc-heading"), 1)

    def test_single_page_toc_has_no_page_break(self):
        html = build_toc_html(self.entries(3))
        self.assertNotIn("page-break", html)


class InsertTocTests(unittest.TestCase):
    def test_replaces_bare_toc_marker(self):
        text = "before\n\n[TOC]\n\nafter"
        result = insert_toc(text, "<ul></ul>")
        self.assertIn("<!-- toc:start -->\n<ul></ul>\n<!-- toc:end -->", result)
        self.assertNotIn("[TOC]", result)

    def test_rerunning_updates_in_place_without_duplicating(self):
        text = "before\n\n[TOC]\n\nafter"
        first = insert_toc(text, "<ul>old</ul>")
        second = insert_toc(first, "<ul>new</ul>")
        self.assertEqual(second.count("<!-- toc:start -->"), 1)
        self.assertIn("<ul>new</ul>", second)
        self.assertNotIn("<ul>old</ul>", second)

    def test_no_marker_leaves_text_untouched(self):
        text = "no marker here"
        result = insert_toc(text, "<ul></ul>")
        self.assertEqual(result, text)


class FindPageNumbersTests(unittest.TestCase):
    def make_headings(self, n):
        return [
            {"id": f"h{i}", "raw_text": f"Heading {i}", "number": str(i + 1)}
            for i in range(n)
        ]

    def rendered(self, heading):
        return f'{heading["number"]}  {heading["raw_text"]}'

    def test_toc_page_is_ignored_without_any_heuristic(self):
        headings = self.make_headings(4)
        toc_page = FakePage(body=[h["raw_text"] for h in headings])
        body_pages = [FakePage(headings=[self.rendered(h)]) for h in headings]
        doc = FakeDoc([toc_page] + body_pages)

        with patched_pymupdf(doc):
            page_numbers = find_page_numbers("fake.pdf", headings)

        for i, heading in enumerate(headings):
            self.assertEqual(page_numbers[heading["id"]], i + 2)

    def test_multi_page_toc_is_ignored(self):
        headings = self.make_headings(10)
        toc_page_1 = FakePage(body=[h["raw_text"] for h in headings[:5]])
        toc_page_2 = FakePage(body=[h["raw_text"] for h in headings[5:]])
        body_pages = [FakePage(headings=[self.rendered(h)]) for h in headings]
        doc = FakeDoc([toc_page_1, toc_page_2] + body_pages)

        with patched_pymupdf(doc):
            page_numbers = find_page_numbers("fake.pdf", headings)

        for i, heading in enumerate(headings):
            self.assertEqual(page_numbers[heading["id"]], i + 3)

    def test_title_page_before_toc_is_skipped(self):
        headings = self.make_headings(5)
        title_page = FakePage()
        toc_page = FakePage(body=[h["raw_text"] for h in headings])
        body_pages = [FakePage(headings=[self.rendered(h)]) for h in headings]
        doc = FakeDoc([title_page, toc_page] + body_pages)

        with patched_pymupdf(doc):
            page_numbers = find_page_numbers("fake.pdf", headings)

        for i, heading in enumerate(headings):
            self.assertEqual(page_numbers[heading["id"]], i + 3)

    def test_many_no_break_headings_on_one_page_all_resolve(self):
        headings = self.make_headings(5)
        toc_page = FakePage(body=[h["raw_text"] for h in headings])
        shared_page = FakePage(headings=[self.rendered(h) for h in headings[:4]])
        last_page = FakePage(headings=[self.rendered(headings[4])])
        doc = FakeDoc([toc_page, shared_page, last_page])

        with patched_pymupdf(doc):
            page_numbers = find_page_numbers("fake.pdf", headings)

        for heading in headings[:4]:
            self.assertEqual(page_numbers[heading["id"]], 2)
        self.assertEqual(page_numbers[headings[4]["id"]], 3)

    def test_prose_cross_reference_is_not_a_false_hit(self):
        headings = self.make_headings(2)
        mention_page = FakePage(
            headings=[self.rendered(headings[0])],
            body=[f'see the {headings[1]["raw_text"]} section'],
        )
        real_page = FakePage(headings=[self.rendered(headings[1])])
        doc = FakeDoc([mention_page, real_page])

        with patched_pymupdf(doc):
            page_numbers = find_page_numbers("fake.pdf", headings)

        self.assertEqual(page_numbers[headings[1]["id"]], 2)

    def test_heading_is_not_matched_as_a_substring_of_another(self):
        headings = [
            {"id": "attendance", "raw_text": "Attendance", "number": "5"},
            {"id": "qr", "raw_text": "Creating attendance QR code", "number": "5.1"},
        ]
        doc = FakeDoc([
            FakePage(headings=[self.rendered(headings[1])]),
            FakePage(headings=[self.rendered(headings[0])]),
            FakePage(headings=[self.rendered(headings[1])]),
        ])

        with patched_pymupdf(doc):
            page_numbers = find_page_numbers("fake.pdf", headings)

        self.assertEqual(page_numbers["attendance"], 2)
        self.assertEqual(page_numbers["qr"], 3)

    def test_heading_wrapped_onto_two_lines_still_matches(self):
        heading = {
            "id": "faq-1",
            "raw_text": "Why does the website on my screen not look the same as in the user guide?",
            "number": "8.1",
        }
        doc = FakeDoc([FakePage(headings=[[
            "8.1  Why does the website on my screen not look the",
            "same as in the user guide?",
        ]])])

        with patched_pymupdf(doc):
            page_numbers = find_page_numbers("fake.pdf", [heading])

        self.assertEqual(page_numbers["faq-1"], 1)

    def test_heading_absent_from_pdf_is_omitted(self):
        headings = self.make_headings(2)
        doc = FakeDoc([FakePage(headings=[self.rendered(headings[0])])])

        with patched_pymupdf(doc):
            page_numbers = find_page_numbers("fake.pdf", headings)

        self.assertEqual(page_numbers[headings[0]["id"]], 1)
        self.assertNotIn(headings[1]["id"], page_numbers)


class TocLengthCorrectionTests(unittest.TestCase):
    def make_headings(self, n):
        return [
            {"id": f"h{i}", "level": 1, "raw_text": f"Heading {i}", "number": str(i + 1)}
            for i in range(n)
        ]

    def rendered(self, heading):
        return f'{heading["number"]}  {heading["raw_text"]}'

    def doc_with_toc_pages(self, headings, toc_pages, lead_pages=0):
        pages = [FakePage() for _ in range(lead_pages)]
        per_page = -(-len(headings) // toc_pages)
        for start in range(0, len(headings), per_page):
            pages.append(FakePage(body=[h["raw_text"] for h in headings[start:start + per_page]]))
        pages += [FakePage(headings=[self.rendered(h)]) for h in headings]
        return FakeDoc(pages)

    def resolve(self, doc, headings, planned_toc_pages):
        with patched_pymupdf(doc), patch("builtins.print"):
            return find_page_numbers("fake.pdf", headings, planned_toc_pages)

    def test_page_numbers_shift_when_the_written_toc_is_longer(self):
        headings = self.make_headings(TOC_ROWS_FIRST_PAGE + 2)
        doc = self.doc_with_toc_pages(headings, toc_pages=1)

        page_numbers = self.resolve(doc, headings, plan_toc_pages(headings))

        for i, heading in enumerate(headings):
            self.assertEqual(page_numbers[heading["id"]], i + 3)

    def test_page_numbers_are_unchanged_once_the_lengths_agree(self):
        headings = self.make_headings(TOC_ROWS_FIRST_PAGE + 2)
        doc = self.doc_with_toc_pages(headings, toc_pages=2)

        page_numbers = self.resolve(doc, headings, plan_toc_pages(headings))

        for i, heading in enumerate(headings):
            self.assertEqual(page_numbers[heading["id"]], i + 3)

    def test_shift_is_negative_when_the_written_toc_is_shorter(self):
        headings = self.make_headings(4)
        doc = self.doc_with_toc_pages(headings, toc_pages=2)

        page_numbers = self.resolve(doc, headings, plan_toc_pages(headings))

        for i, heading in enumerate(headings):
            self.assertEqual(page_numbers[heading["id"]], i + 2)

    def test_title_page_is_not_counted_as_part_of_the_toc(self):
        headings = self.make_headings(TOC_ROWS_FIRST_PAGE + 2)
        doc = self.doc_with_toc_pages(headings, toc_pages=1, lead_pages=1)

        page_numbers = self.resolve(doc, headings, plan_toc_pages(headings))

        for i, heading in enumerate(headings):
            self.assertEqual(page_numbers[heading["id"]], i + 4)

    def test_omitting_the_planned_length_leaves_the_pdf_numbers_alone(self):
        headings = self.make_headings(TOC_ROWS_FIRST_PAGE + 2)
        doc = self.doc_with_toc_pages(headings, toc_pages=1)

        with patched_pymupdf(doc), patch("builtins.print"):
            page_numbers = find_page_numbers("fake.pdf", headings)

        for i, heading in enumerate(headings):
            self.assertEqual(page_numbers[heading["id"]], i + 2)

    def test_an_export_with_no_toc_at_all_shifts_by_the_whole_toc(self):
        headings = self.make_headings(2)
        doc = FakeDoc([FakePage(headings=[self.rendered(h)]) for h in headings])

        page_numbers = self.resolve(doc, headings, planned_toc_pages=2)

        self.assertEqual(page_numbers[headings[0]["id"]], 3)
        self.assertEqual(page_numbers[headings[1]["id"]], 4)

    def test_no_shift_can_push_a_heading_off_the_front_of_the_document(self):
        headings = self.make_headings(8)
        doc = self.doc_with_toc_pages(headings, toc_pages=4)

        page_numbers = self.resolve(doc, headings, planned_toc_pages=1)

        self.assertEqual(min(page_numbers.values()), 2)


class PdfInputTests(unittest.TestCase):
    def make_headings(self, n):
        return [
            {"id": f"h{i}", "level": 1, "raw_text": f"Heading {i}", "number": str(i + 1)}
            for i in range(n)
        ]

    def test_markdown_passed_as_pdf_is_rejected(self):
        doc = FakeDoc([FakePage()], is_pdf=False)
        with patched_pymupdf(doc):
            with self.assertRaises(PdfInputError):
                find_page_numbers("userguide_res.md", self.make_headings(1))

    def test_unopenable_pdf_is_reported_not_traced(self):
        fake_module = types.ModuleType("pymupdf")

        def explode(path):
            raise FileNotFoundError(path)

        fake_module.open = explode
        with patch.dict(sys.modules, {"pymupdf": fake_module}):
            with self.assertRaises(PdfInputError):
                find_page_numbers("gone.pdf", self.make_headings(1))


class MissingPageNumberReportTests(unittest.TestCase):
    def make_headings(self, n):
        return [
            {"id": f"h{i}", "level": 1, "raw_text": f"Heading {i}", "number": str(i + 1)}
            for i in range(n)
        ]

    def rendered(self, heading):
        return f'{heading["number"]}  {heading["raw_text"]}'

    def output_of(self, doc, headings):
        with patched_pymupdf(doc), patch("builtins.print") as fake_print:
            find_page_numbers("fake.pdf", headings)
        return "\n".join(str(call.args[0]) for call in fake_print.call_args_list)

    def test_partial_failure_is_reported_on_the_console(self):
        headings = self.make_headings(3)
        doc = FakeDoc([FakePage(headings=[self.rendered(headings[0])])])

        output = self.output_of(doc, headings)

        self.assertIn("[WARN]", output)
        self.assertIn("2 of 3", output)

    def test_nothing_is_warned_when_every_heading_resolves(self):
        headings = self.make_headings(2)
        doc = FakeDoc([
            FakePage(headings=[self.rendered(headings[0])]),
            FakePage(headings=[self.rendered(headings[1])]),
        ])

        self.assertNotIn("[WARN]", self.output_of(doc, headings))

    def test_unstyled_export_is_named_as_the_cause(self):
        headings = self.make_headings(2)
        doc = FakeDoc([FakePage(headings=["Heading 0"])])

        output = self.output_of(doc, headings)

        self.assertIn("[WARN]", output)
        self.assertIn("WITHOUT styles.css", output)

    def test_wrong_export_is_not_blamed_on_styles(self):
        headings = self.make_headings(2)
        doc = FakeDoc([FakePage(headings=[self.rendered(headings[0])])])

        output = self.output_of(doc, headings)

        self.assertIn("[WARN]", output)
        self.assertNotIn("WITHOUT styles.css", output)


class TocHeadingTests(unittest.TestCase):
    def test_toc_block_starts_with_a_table_of_contents_title(self):
        headings = parse_headings("# Quick Start\n")
        assign_ids(headings)
        assign_numbers(headings)
        html = build_toc_html(headings)
        self.assertTrue(html.startswith('<div class="toc-heading">Table of Contents</div>'))

    def test_title_is_not_a_heading_so_a_re_run_cannot_list_it(self):
        headings = parse_headings("# Quick Start\n")
        assign_ids(headings)
        assign_numbers(headings)
        html = build_toc_html(headings)
        self.assertEqual(parse_headings(html), [])


if __name__ == "__main__":
    unittest.main()
