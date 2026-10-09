import argparse
import logging
import re
import settings
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent


def userguide_res_filename():
    return settings.result_filename(settings.USERGUIDE_FILENAME)

TOC_START = "<!-- toc:start -->"
TOC_END = "<!-- toc:end -->"

TOC_HEADING_TEXT = "Table of Contents"

HEADING_MIN_FONT_SIZE = 18.0

TOC_ROWS_FIRST_PAGE = 28
TOC_ROWS_PER_PAGE = 31

TOC_PAGE_MIN_ENTRIES = 2

ATX_HEADING_RE = re.compile(r'^(#{1,2})[ \t]+(.+?)[ \t]*$', re.MULTILINE)

ATTR_VALUE = r'''(?:"[^"]*"|'[^']*'|[^\s>"'`=]+)'''

HTML_HEADING_RE = re.compile(
    r'^<h([12])((?:\s+[\w-]+(?:=' + ATTR_VALUE + r')?)*)\s*>(.*?)</h\1>[ \t]*$',
    re.MULTILINE,
)

ID_ATTR_RE = re.compile(r'(?<![\w-])id=(?:"([^"]*)"|\'([^\']*)\'|([^\s>"\'`=]+))')


def strip_markdown_emphasis(text):
    return re.sub(r'[*_`]', '', text)


def slugify(text, used_slugs):
    text = strip_markdown_emphasis(text).lower()
    slug = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    if not slug:
        slug = "section"
    if slug in used_slugs:
        n = 1
        while f"{slug}-{n}" in used_slugs:
            n += 1
        slug = f"{slug}-{n}"
    used_slugs.add(slug)
    return slug


def extract_existing_id(attrs):
    match = ID_ATTR_RE.search(attrs or "")
    if not match:
        return None
    return next(group for group in match.groups() if group is not None)


def strip_id_attr(attrs):
    return re.sub(r'\s*' + ID_ATTR_RE.pattern, '', attrs or "")


def parse_headings(text):
    headings = []
    for match in ATX_HEADING_RE.finditer(text):
        headings.append({
            "level": len(match.group(1)),
            "raw_text": match.group(2),
            "attrs": "",
            "span": match.span(),
        })
    for match in HTML_HEADING_RE.finditer(text):
        headings.append({
            "level": int(match.group(1)),
            "raw_text": match.group(3),
            "attrs": match.group(2),
            "span": match.span(),
        })
    headings.sort(key=lambda h: h["span"][0])
    return headings


def assign_ids(headings):
    used_slugs = set()
    for heading in headings:
        existing_id = extract_existing_id(heading["attrs"])
        if existing_id:
            used_slugs.add(existing_id)
            heading["id"] = existing_id
        else:
            heading["id"] = slugify(heading["raw_text"], used_slugs)
    return headings


def rewrite_headings(text, headings):
    pieces = []
    cursor = 0
    for heading in headings:
        start, end = heading["span"]
        pieces.append(text[cursor:start])
        attrs = strip_id_attr(heading["attrs"])
        id_attr = f' id="{heading["id"]}"'
        pieces.append(f'<h{heading["level"]}{attrs}{id_attr}>{heading["raw_text"]}</h{heading["level"]}>')
        cursor = end
        if cursor < len(text) and text[cursor] == "\n" and text[cursor:cursor + 2] != "\n\n":
            pieces.append("\n")
    pieces.append(text[cursor:])
    return "".join(pieces)


def chunk_toc_entries(headings):
    chunks = []
    remaining = list(headings)
    capacity = TOC_ROWS_FIRST_PAGE
    while True:
        chunks.append(remaining[:capacity])
        remaining = remaining[capacity:]
        if not remaining:
            return chunks
        capacity = TOC_ROWS_PER_PAGE


def plan_toc_pages(headings):
    return len(chunk_toc_entries(headings))


def assign_numbers(headings):
    h1_counter = 0
    h2_counter = 0
    for heading in headings:
        if heading["level"] == 1:
            h1_counter += 1
            h2_counter = 0
            heading["number"] = str(h1_counter)
        else:
            h2_counter += 1
            heading["number"] = f"{h1_counter}.{h2_counter}"
    return headings


def render_toc_entry(heading, page_numbers):
    clean_text = strip_markdown_emphasis(heading["raw_text"])
    page = (page_numbers or {}).get(heading["id"])
    page_html = f'<span class="toc-page">{page}</span>' if page else ""
    return (
        f'<a href="#{heading["id"]}">'
        f'<span class="toc-number">{heading["number"]}</span>'
        f'<span class="toc-title">{clean_text}</span>'
        f'<span class="toc-dots"></span>'
        f'{page_html}'
        f'</a>'
    )


def build_toc_html(headings, page_numbers=None):
    lines = [f'<div class="toc-heading">{TOC_HEADING_TEXT}</div>']
    for index, chunk in enumerate(chunk_toc_entries(headings)):
        if index:
            lines.append('<div class="page-break"></div>')
        lines.append('<ul class="toc">')
        for heading in chunk:
            entry = render_toc_entry(heading, page_numbers)
            lines.append(f'  <li class="toc-h{heading["level"]}">{entry}</li>')
        lines.append('</ul>')
    return "\n".join(lines)


def insert_toc(text, toc_html):
    block = f"{TOC_START}\n{toc_html}\n{TOC_END}"
    existing_block_re = re.compile(
        re.escape(TOC_START) + r'.*?' + re.escape(TOC_END), re.DOTALL
    )
    if existing_block_re.search(text):
        return existing_block_re.sub(lambda m: block, text, count=1)
    if "[TOC]" in text:
        return text.replace("[TOC]", block, 1)
    logger.error("No [TOC] marker or existing toc:start/toc:end block found - TOC not inserted.")
    print("[WARN] No [TOC] marker or existing <!-- toc:start --> block found; TOC was not inserted.")
    return text


def normalize_space(text):
    return re.sub(r'\s+', ' ', text).strip()


def extract_heading_runs(page):
    runs = []
    for block in page.get_text("dict")["blocks"]:
        current = []
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = "".join(span["text"] for span in spans)
            if not text.strip():
                continue
            if spans and max(span["size"] for span in spans) >= HEADING_MIN_FONT_SIZE:
                current.append(text)
            elif current:
                runs.append(current)
                current = []
        if current:
            runs.append(current)
    return runs


def extract_body_lines(page):
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = normalize_space("".join(span["text"] for span in spans))
            if text and max(span["size"] for span in spans) < HEADING_MIN_FONT_SIZE:
                lines.append(text)
    return lines


def count_rendered_toc_pages(doc, headings, first_body_page):
    titles = [normalize_space(strip_markdown_emphasis(h["raw_text"])) for h in headings]
    if not titles:
        return 0
    threshold = min(TOC_PAGE_MIN_ENTRIES, len(titles))
    pages = 0
    for page_index in range(min(first_body_page - 1, doc.page_count)):
        hits = 0
        for line in extract_body_lines(doc[page_index]):
            if any(line == title or line.endswith(title) for title in titles):
                hits += 1
        if hits >= threshold:
            pages += 1
    return pages


def shift_page_numbers(page_numbers, shift):
    return {key: page + shift for key, page in page_numbers.items()}


def correct_for_toc_length(doc, headings, page_numbers, planned_toc_pages):
    first_body_page = min(page_numbers.values())
    rendered_toc_pages = count_rendered_toc_pages(doc, headings, first_body_page)
    shift = planned_toc_pages - rendered_toc_pages
    report_toc_length(rendered_toc_pages, planned_toc_pages, shift)
    return shift_page_numbers(page_numbers, shift) if shift else page_numbers


def report_toc_length(rendered_toc_pages, planned_toc_pages, shift):
    message = (
        f"Table of contents: {rendered_toc_pages} page(s) in the PDF, "
        f"{planned_toc_pages} page(s) in the TOC being written."
    )
    print(f"[INFO] {message}")
    logger.info(message)
    if not shift:
        return
    print(f"       Every page number read from the PDF is therefore shifted by {shift:+d}.")
    print("       Re-export the PDF from this file and re-run to confirm - the two")
    print("       page counts should then match and the shift should be 0.")
    logger.info(f"Shifted every page number by {shift:+d} to match the new TOC length.")


def heading_matches(rendered, number, title):
    if rendered == title:
        return True
    if not rendered.endswith(title):
        return False
    return rendered[: len(rendered) - len(title)].strip() == number


def page_has_heading(runs, number, title):
    for run in runs:
        for start in range(len(run)):
            for end in range(start + 1, len(run) + 1):
                if heading_matches(normalize_space(" ".join(run[start:end])), number, title):
                    return True
    return False


def find_page_numbers(pdf_path, headings, planned_toc_pages=None):
    try:
        import pymupdf
    except ImportError:
        print("[WARN] --pdf given but PyMuPDF isn't installed (pip install pymupdf); skipping page numbers.")
        return {}

    doc = open_pdf(pymupdf, pdf_path)
    runs_by_page = [extract_heading_runs(doc[i]) for i in range(doc.page_count)]
    describe_pdf(pdf_path, doc)

    page_numbers = {}
    missing = []
    start_page = 0
    for heading in headings:
        title = normalize_space(strip_markdown_emphasis(heading["raw_text"]))
        number = heading.get("number", "")
        found = None
        for page_index in range(start_page, doc.page_count):
            if page_has_heading(runs_by_page[page_index], number, title):
                found = page_index + 1
                start_page = page_index
                break
        if found:
            page_numbers[heading["id"]] = found
        else:
            missing.append(f"{number}  {title}")
            logger.error(f"Heading '{title}' not found in PDF for page-number lookup.")
    if missing:
        log_heading_sized_text(runs_by_page)
    unstyled = missing and looks_unstyled(runs_by_page)
    if planned_toc_pages is not None and page_numbers:
        page_numbers = correct_for_toc_length(doc, headings, page_numbers, planned_toc_pages)
    doc.close()
    report_missing_page_numbers(missing, len(headings), unstyled=unstyled)
    return page_numbers


def looks_unstyled(runs_by_page):
    saw_heading_text = False
    for runs in runs_by_page:
        for run in runs:
            for line in run:
                text = normalize_space(line)
                if not text:
                    continue
                saw_heading_text = True
                if re.match(r'^\d+(\.\d+)*\s', text):
                    return False
    return saw_heading_text


class PdfInputError(Exception):
    pass


def open_pdf(pymupdf, pdf_path):
    path = Path(pdf_path)
    try:
        doc = pymupdf.open(path)
    except (FileNotFoundError, RuntimeError) as exc:
        raise PdfInputError(f"--pdf could not be opened: {path.resolve()}\n       {exc}") from exc

    if not doc.is_pdf:
        page_count = doc.page_count
        doc.close()
        raise PdfInputError(
            f"--pdf is not a PDF: {path.resolve()}\n"
            f"       PyMuPDF opened it anyway (as a {page_count}-page rendering of its "
            f"text), which would have produced\n"
            f"       wrong page numbers rather than an error. Pass the exported PDF, "
            f"e.g. {userguide_res_filename().replace('.md', '.pdf')}."
        )
    return doc


def describe_pdf(pdf_path, doc):
    resolved = Path(pdf_path).resolve()
    try:
        stat = resolved.stat()
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        detail = f", {stat.st_size} bytes, modified {modified}"
    except OSError:
        detail = ""
    message = f"Reading page numbers from {resolved} ({doc.page_count} page(s){detail})."
    print(f"[INFO] {message}")
    logger.info(message)


def log_heading_sized_text(runs_by_page):
    logger.error("Heading-sized text found in the PDF, page by page:")
    for page_index, runs in enumerate(runs_by_page):
        for run in runs:
            logger.error(f"  p{page_index + 1}: {normalize_space(' '.join(run))}")


def report_missing_page_numbers(missing, total, sample_size=5, unstyled=False):
    if not missing:
        return
    print(f"[WARN] {len(missing)} of {total} heading(s) had no page number resolved from the PDF:")
    for entry in missing[:sample_size]:
        print(f"          {entry}")
    if len(missing) > sample_size:
        print(f"          ... and {len(missing) - sample_size} more (full list in {settings.LOG_PATH}).")
    print("       Those TOC entries render with no page number.")
    if unstyled:
        print("       This PDF has no section numbers on any heading, so it was exported")
        print("       WITHOUT styles.css. Such an export also sets h2 below the heading")
        print("       font-size threshold and drops every page break, so h2s can never be")
        print("       found in it and the h1 pages it does yield are wrong. Re-export with")
        print("       the stylesheet applied (Markdown Preview Enhanced -> Chrome (Puppeteer)")
        print("       -> PDF, from userguide_res.md so its <link> to styles.css resolves).")
    else:
        print("       The usual cause is a --pdf that isn't the current export: re-export")
        print("       the PDF from the current userguide_res.md, then re-run against it.")


def generate_toc(filename=None, pdf_path=None):
    filename = filename or userguide_res_filename()
    path = settings.PARENT_PATH / filename
    text = path.read_text(encoding="utf-8")

    headings = parse_headings(text)
    if not headings:
        print("[WARN] No h1/h2 headings found; nothing to do.")
        return

    assign_ids(headings)
    assign_numbers(headings)
    text = rewrite_headings(text, headings)

    page_numbers = None
    if pdf_path:
        page_numbers = find_page_numbers(pdf_path, headings, plan_toc_pages(headings))

    toc_html = build_toc_html(headings, page_numbers)
    text = insert_toc(text, toc_html)

    path.write_text(text, encoding="utf-8")
    print(f"[SUCCESS] Rewrote {len(headings)} heading(s) with explicit ids and inserted the TOC into {filename}.")
    if pdf_path:
        print(f"[INFO] {len(page_numbers)} of {len(headings)} TOC entry(s) got a page number.")


def main():
    settings.configure_logging()
    default_file = userguide_res_filename()
    parser = argparse.ArgumentParser(description="Generate a TOC for the expanded user guide with explicit heading ids.")
    parser.add_argument("--file", default=default_file, help=f"File to rewrite (default: {default_file})")
    parser.add_argument(
        "--pdf",
        default=None,
        help=(
            "Path to an already-exported PDF (not the markdown), to annotate the TOC "
            f"with page numbers, e.g. {default_file.replace('.md', '.pdf')}"
        ),
    )
    args = parser.parse_args()
    try:
        generate_toc(args.file, args.pdf)
    except PdfInputError as exc:
        logger.error(str(exc))
        print(f"[ERROR] {exc}")
        print(f"       {args.file} was not modified.")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
