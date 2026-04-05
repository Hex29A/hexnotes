from backend.main import (
    generate_slug,
    extract_tags,
    parse_frontmatter,
    strip_frontmatter,
    created_at_from_filename,
    sanitize_filename,
)


# === Slug generation ===

def test_slug_basic():
    assert generate_slug("Docker compose tips") == "docker-compose-tips"


def test_slug_strips_tags():
    assert generate_slug("Min anteckning #docker #linux") == "min-anteckning"


def test_slug_strips_special_chars():
    assert generate_slug("Hej! Vad händer?") == "hej-vad-händer"


def test_slug_max_length():
    long = "a" * 100
    assert len(generate_slug(long)) <= 60


def test_slug_empty_returns_untitled():
    assert generate_slug("") == "untitled"
    assert generate_slug("   ") == "untitled"


def test_slug_only_tags_returns_untitled():
    assert generate_slug("#docker #linux") == "untitled"


# === Tag extraction ===

def test_extract_tags_basic():
    assert extract_tags("hello #docker #linux") == ["docker", "linux"]


def test_extract_tags_none():
    assert extract_tags("ingen taggar här") == []


def test_extract_tags_deduplication():
    assert extract_tags("#docker #docker #linux") == ["docker", "linux"]


def test_extract_tags_ignores_urls():
    assert "example" not in extract_tags("https://example.com/#section")


def test_extract_tags_case_preserved():
    assert extract_tags("#Docker") == ["Docker"]


# === Frontmatter parsing ===

FRONTMATTER_DOC = """---
tags: [docker, linux]
created: 2025-04-03
---
Innehåll här
"""


def test_parse_frontmatter_tags():
    meta, _ = parse_frontmatter(FRONTMATTER_DOC)
    assert meta["tags"] == ["docker", "linux"]


def test_parse_frontmatter_created():
    meta, _ = parse_frontmatter(FRONTMATTER_DOC)
    assert str(meta["created"]) == "2025-04-03"


def test_strip_frontmatter_returns_content():
    _, body = parse_frontmatter(FRONTMATTER_DOC)
    assert body.strip() == "Innehåll här"


def test_parse_frontmatter_missing():
    meta, body = parse_frontmatter("Ingen frontmatter här\n#docker")
    assert meta == {}
    assert "Ingen frontmatter" in body


def test_parse_frontmatter_empty_tags():
    doc = "---\ntags: []\ncreated: 2025-04-03\n---\nInnehåll"
    meta, _ = parse_frontmatter(doc)
    assert meta["tags"] == []


# === created_at from filename ===

def test_created_at_datumprefix():
    assert created_at_from_filename("2025-04-03-docker-tips.md") == "2025-04-03"


def test_created_at_timeless():
    assert created_at_from_filename("ideas.md") is None


def test_created_at_invalid_prefix():
    assert created_at_from_filename("notadate-docker.md") is None


def test_created_at_only_date():
    assert created_at_from_filename("2025-04-03.md") == "2025-04-03"


# === Filename sanitization ===

def test_sanitize_adds_md_extension():
    assert sanitize_filename("ideas") == "ideas.md"


def test_sanitize_preserves_md():
    assert sanitize_filename("ideas.md") == "ideas.md"


def test_sanitize_strips_path_traversal():
    assert "/" not in sanitize_filename("../../etc/passwd")
    assert ".." not in sanitize_filename("../../etc/passwd")


def test_sanitize_strips_leading_dot():
    assert not sanitize_filename(".hidden").startswith(".")
