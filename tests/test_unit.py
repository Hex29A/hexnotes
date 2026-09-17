from backend.main import (
    extract_tags,
    parse_frontmatter,
    created_at_from_filename,
    sanitize_filename,
)


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


def test_parse_frontmatter_returns_body_without_frontmatter():
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


# === Startup seeding ===

def test_startup_seeds_home_when_empty(tmp_notes):
    import asyncio
    from backend import main
    asyncio.run(main.startup())
    assert (tmp_notes / "home.md").exists()
    assert "home" in main.notes_index


def test_startup_leaves_existing_notes_alone(tmp_notes):
    import asyncio
    from backend import main
    (tmp_notes / "existing.md").write_text("hello", encoding="utf-8")
    asyncio.run(main.startup())
    assert not (tmp_notes / "home.md").exists()


# === Frontmatter is built with YAML, not string formatting ===

def test_frontmatter_matches_the_old_shape_for_ordinary_notes():
    """Byte för byte som förut — 161 noter på disk ska inte skrivas om
    kosmetiskt bara för att byggaren bytte till safe_dump."""
    from backend.main import _build_frontmatter
    nl = chr(10)
    assert _build_frontmatter(["genetec"], "2026-04-10") == (
        "---" + nl + "tags: [genetec]" + nl + "created: 2026-04-10" + nl + "---" + nl
    )
    assert _build_frontmatter([], None) == (
        "---" + nl + "tags: []" + nl + "created: null" + nl + "---" + nl
    )


def test_frontmatter_escapes_a_created_value_with_a_newline():
    """En nyrad i created öppnade förut en egen frontmatter-rad, så en not
    kunde få fält (pinned) som inget API-anrop satt."""
    from backend.main import _build_frontmatter, parse_frontmatter
    fm = _build_frontmatter([], "2026-01-01" + chr(10) + "pinned: true")
    meta, _ = parse_frontmatter(fm)
    assert "pinned" not in meta
    assert meta["created"] == "2026-01-01" + chr(10) + "pinned: true"


def test_frontmatter_survives_a_round_trip(tmp_notes):
    """Skriv → läs → skriv får inte ändra vad noten säger om sig själv."""
    from backend.main import _write_note_with_frontmatter, parse_note
    path = tmp_notes / "rundtur.md"
    _write_note_with_frontmatter(path, "text #tagg", "2026-04-10", True, "2026-09-17T22:59:21+00:00")
    first = path.read_text(encoding="utf-8")
    note = parse_note(path)
    _write_note_with_frontmatter(path, note["content"], "2026-04-10", note["pinned"], note["expires_at"])
    assert path.read_text(encoding="utf-8") == first


# === Expiry parsing ===

def test_normalize_expiry_repairs_the_space_separated_form():
    """Noter som redan ligger på disk i det trasiga formatet ska läsas rätt."""
    from backend.main import normalize_expiry, parse_expiry
    assert normalize_expiry("2026-09-17 22:59:21+00:00") == "2026-09-17T22:59:21+00:00"
    assert parse_expiry("2026-09-17 22:59:21+00:00").hour == 22


def test_parse_expiry_assumes_utc_when_the_zone_is_missing():
    from datetime import UTC
    from backend.main import parse_expiry
    assert parse_expiry("2026-09-17T22:59:21").tzinfo is UTC


def test_parse_expiry_returns_none_on_junk():
    from backend.main import parse_expiry
    assert parse_expiry("inte-en-tid") is None
    assert parse_expiry(None) is None
    assert parse_expiry("") is None


def test_frontmatter_keeps_leading_whitespace_in_the_body():
    """\\s* efter den avslutande ---raden åt in i brödtexten: \\s matchar
    nyrader och mellanslag lika, så en not som började med ett blanksteg
    eller en tomrad tappade det tecknet vid varje sparning."""
    nl = chr(10)
    doc = "---" + nl + "tags: []" + nl + "---" + nl + " indragen första rad"
    _, body = parse_frontmatter(doc)
    assert body == " indragen första rad"

    doc2 = "---" + nl + "tags: []" + nl + "---" + nl + nl + "efter tomrad"
    _, body2 = parse_frontmatter(doc2)
    assert body2 == nl + "efter tomrad"


def test_frontmatter_without_trailing_newline_still_parses():
    """En fil som slutar direkt efter den avslutande ---raden."""
    nl = chr(10)
    meta, body = parse_frontmatter("---" + nl + "tags: []" + nl + "---")
    assert meta == {"tags": []}
    assert body == ""
