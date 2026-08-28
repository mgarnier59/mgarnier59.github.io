#!/usr/bin/env python3

import argparse
import re
from pathlib import Path

import bibtexparser


def clean_latex(text):
    """Remove/convert a few common LaTeX constructs."""

    if not text:
        return ""

    # Protect escaped special characters
    replacements = {
        r"\&": "&",
        r"\%": "%",
        r"\_": "_",
        r"\#": "#",
        r"\$": "$",
        r"\{": "{",
        r"\}": "}",
        r"---": "—",
        r"--": "–",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove remaining braces used for capitalization protection
    text = text.replace("{", "").replace("}", "")

    return text.strip()


def parse_keywords(entry):
    """
    Return BibTeX keywords as a lowercase list.

    Example:
        keywords = {paper,phd}
    becomes:
        ["paper", "phd"]
    """

    keywords = entry.get("keywords", "")

    if not keywords:
        return []

    return [
        keyword.strip().lower()
        for keyword in keywords.split(",")
        if keyword.strip()
    ]


def format_authors(author_string):
    """
    Convert BibTeX author names into a readable citation.

    Example:
        Garnier, Maxime and Mesaros, Andrej

    becomes:
        Maxime Garnier, Andrej Mesaros
    """

    if not author_string:
        return ""

    authors = []

    for author in author_string.split(" and "):
        author = author.strip()

        if "," in author:
            parts = [p.strip() for p in author.split(",", 1)]
            last = parts[0]
            first = parts[1]
            authors.append(f"{first} {last}")
        else:
            authors.append(author)

    return ", ".join(authors)


def format_date(entry):
    """
    Generate a date suitable for Academic Pages.

    If month/day are available:
        2019-10-17

    If only year is available:
        2025-01-01

    The January 1 fallback is useful for Jekyll sorting.
    """

    year = entry.get("year", "").strip()

    if not year:
        return ""

    month = entry.get("month", "").strip()
    day = entry.get("day", "").strip()

    try:
        month = int(month) if month else 1
    except ValueError:
        month = 1

    try:
        day = int(day) if day else 1
    except ValueError:
        day = 1

    return f"{int(year):04d}-{month:02d}-{day:02d}"


def make_citation(entry):
    """Create a simple human-readable citation."""

    authors = format_authors(entry.get("author", ""))
    year = entry.get("year", "")
    title = clean_latex(entry.get("title", ""))

    venue = (
        entry.get("journal")
        or entry.get("booktitle")
        or ""
    )

    venue = clean_latex(venue)

    # arXiv information
    eprint = entry.get("eprint", "").strip()
    archive = entry.get("archiveprefix", "").strip()

    if eprint and archive.lower() == "arxiv":
        venue = f"arXiv:{eprint}"

    parts = []

    if authors:
        parts.append(authors)

    if year:
        parts.append(f"({year})")

    if title:
        parts.append(f"{title}.")

    if venue:
        parts.append(venue + ".")

    return " ".join(parts)


def make_permalink(entry):
    """Generate a stable Academic Pages URL from the BibTeX key."""

    key = entry.get("ID", "").strip()

    # Keep the BibTeX key stable and URL-friendly
    key = re.sub(r"[^A-Za-z0-9_-]", "-", key)

    return f"/publication/{key}"


def make_filename(entry):
    """Generate the Markdown filename."""

    key = entry.get("ID", "").strip()
    year = entry.get("year", "").strip()

    key = re.sub(r"[^A-Za-z0-9_-]", "-", key)

    if year:
        return f"{year}-{key}.md"

    return f"{key}.md"


def make_markdown(entry, collection, category):
    """Generate the complete Academic Pages Markdown file."""

    title = clean_latex(entry.get("title", "Untitled"))
    date = format_date(entry)
    venue = clean_latex(
        entry.get("journal")
        or entry.get("booktitle")
        or ""
    )

    url = entry.get("url", "").strip()
    doi = entry.get("doi", "").strip()

    # Prefer DOI if there is no explicit URL
    if not url and doi:
        url = f"https://doi.org/{doi}"

    # For arXiv, construct URL if necessary
    eprint = entry.get("eprint", "").strip()
    archive = entry.get("archiveprefix", "").strip()

    if not url and eprint and archive.lower() == "arxiv":
        url = f"https://arxiv.org/abs/{eprint}"

    citation = make_citation(entry)
    permalink = make_permalink(entry)

    lines = [
        "---",
        f'title: "{title.replace(chr(34), chr(92) + chr(34))}"',
        f"collection: {collection}",
        f"category: {category}",
        f"permalink: {permalink}",
    ]

    if date:
        lines.append(f"date: {date}")

    if venue:
        lines.append(f'venue: "{venue.replace(chr(34), chr(92) + chr(34))}"')

    if url:
        lines.append(f'paperurl: "{url}"')

    if citation:
        citation_escaped = citation.replace('"', '\\"')
        lines.append(f'citation: "{citation_escaped}"')

        lines.extend(
        [
            "---",
            "",
        ]
    )

    abstract = clean_latex(entry.get("abstract", ""))

    if abstract:
        lines.extend(
            [
                "## Abstract",
                "",
                abstract,
                "",
            ]
        )

    return "\n".join(lines)


def main():

    parser = argparse.ArgumentParser(
        description="Generate Academic Pages Markdown files from BibTeX."
    )

    parser.add_argument(
        "--bib",
        default="bibliography/mypapers.bib",
        help="Path to the BibTeX file.",
    )

    parser.add_argument(
        "--keyword",
        required=True,
        help="BibTeX keyword to select, e.g. preprint or paper.",
    )

    parser.add_argument(
        "--output",
        default="_publications",
        help="Output directory.",
    )

    parser.add_argument(
        "--collection",
        default="publications",
        help="Academic Pages collection name.",
    )

    parser.add_argument(
        "--category",
        default=None,
        help="Academic Pages category. Defaults to the keyword.",
    )

    args = parser.parse_args()

    bib_path = Path(args.bib)
    output_dir = Path(args.output)

    if not bib_path.exists():
        raise FileNotFoundError(
            f"BibTeX file not found: {bib_path}"
        )

    # Read BibTeX
    with bib_path.open("r", encoding="utf-8") as bib_file:
        bib_database = bibtexparser.load(bib_file)

    output_dir.mkdir(parents=True, exist_ok=True)

    keyword = args.keyword.lower().strip()
    category = args.category or keyword

    generated = 0

    for entry in bib_database.entries:

        keywords = parse_keywords(entry)

        if keyword not in keywords:
            continue

        filename = make_filename(entry)
        output_path = output_dir / filename

        markdown = make_markdown(
            entry=entry,
            collection=args.collection,
            category=category,
        )

        output_path.write_text(
            markdown,
            encoding="utf-8",
        )

        print(f"Generated: {output_path}")

        generated += 1

    print()
    print(
        f"Generated {generated} entries "
        f"with keyword '{keyword}'."
    )


if __name__ == "__main__":
    main()
