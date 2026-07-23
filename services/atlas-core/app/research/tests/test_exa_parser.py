from __future__ import annotations

from app.research.parsers.exa import ExaParser


def test_parse_multiple_results() -> None:
    parser = ExaParser()

    response = {
        "content": [
            {
                "type": "text",
                "text": (
                    "Title: First Result\n"
                    "URL: https://example.com/first\n"
                    "Published: 2026-07-20T00:00:00.000Z\n"
                    "Author: Alice\n"
                    "Highlights:\n"
                    "First result content.\n"
                    "\n---\n"
                    "Title: Second Result\n"
                    "URL: https://example.com/second\n"
                    "Published: N/A\n"
                    "Author: N/A\n"
                    "Highlights:\n"
                    "Second result content."
                ),
                "_meta": {
                    "searchTime": 1.25,
                },
            }
        ]
    }

    documents = parser.parse(response)

    assert len(documents) == 2

    assert documents[0].title == "First Result"
    assert documents[0].url == "https://example.com/first"
    assert documents[0].published == "2026-07-20T00:00:00.000Z"
    assert documents[0].author == "Alice"
    assert documents[0].content == "First result content."
    assert documents[0].source == "exa"
    assert documents[0].provider == "mcp"
    assert documents[0].metadata["search_time_seconds"] == 1.25

    assert documents[1].title == "Second Result"
    assert documents[1].published is None
    assert documents[1].author is None
    assert documents[1].content == "Second result content."


def test_parse_empty_content() -> None:
    parser = ExaParser()

    assert parser.parse({"content": []}) == []


def test_parse_missing_content_key() -> None:
    parser = ExaParser()

    assert parser.parse({}) == []


def test_parse_skips_result_without_url() -> None:
    parser = ExaParser()

    response = {
        "content": [
            {
                "type": "text",
                "text": (
                    "Title: Missing URL\n"
                    "Published: 2026-07-20T00:00:00.000Z\n"
                    "Author: Alice\n"
                    "Highlights:\n"
                    "This result should be skipped."
                ),
            }
        ]
    }

    assert parser.parse(response) == []


def test_parse_uses_url_when_title_missing() -> None:
    parser = ExaParser()

    response = {
        "content": [
            {
                "type": "text",
                "text": (
                    "Title: N/A\n"
                    "URL: https://example.com/no-title\n"
                    "Published: N/A\n"
                    "Author: N/A\n"
                    "Highlights:\n"
                    "Content without a useful title."
                ),
            }
        ]
    }

    documents = parser.parse(response)

    assert len(documents) == 1
    assert documents[0].title == "https://example.com/no-title"