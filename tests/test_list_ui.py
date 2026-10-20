"""Regression checks for the sidebar note list: errors and ordering."""
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text(encoding="utf-8")


def _function(name):
    start = SRC.index(f"function {name}(")
    end = SRC.index("\n}\n", start)
    return SRC[start:end]


def test_failed_note_load_is_shown_not_swallowed():
    """Regression: the proxy being down gave an empty list with no error, which
    looked as if every note was gone. See #13."""
    assert 'id="list-error"' in SRC
    for name in ("loadNotes", "pollNotes"):
        body = _function(name)
        assert "showListError(err)" in body, f"{name} still swallows the error"
        assert "clearListError()" in body, f"{name} does not clear the error on a successful fetch"


def test_list_error_distinguishes_network_from_http_status():
    body = _function("showListError")
    assert "err.status === 401" in body
    assert "goOffline()" in body
    assert "fetchAllNotes" not in body
    assert "err.status = res.status" in _function("fetchAllNotes")


def test_coming_back_online_reloads_the_list():
    assert "loadNotes();" in _function("goOnline")


def test_groups_sort_newest_created_first():
    """Within each group the most recently created note comes first. See #14."""
    assert "b.created_at" in _function("sortNewestCreated")
    assert "sortNewestCreated(groupNotes)" in _function("renderNoteGroup")


def test_all_notes_group_holds_every_unpinned_note():
    """Inbox only showed untagged notes, so a tagged journal note did not show
    at the top after a refresh (2026-10-07). All notes includes every unpinned
    note."""
    body = _function("renderNotesList")
    assert "'<span>All notes</span>', unpinned," in body
    assert "n.tags.length === 0" not in body
    assert "<span>Inbox</span>" not in SRC


def test_all_notes_sorted_by_last_edit_under_date_headings():
    assert "b.updated_at" in _function("sortRecentlyUpdated")
    assert "b.created_at" not in _function("sortRecentlyUpdated")
    fill = _function("appendDateBuckets")
    assert "sortRecentlyUpdated(list)" in fill
    assert "dateBucket(n.updated_at)" in fill
    buckets = _function("dateBucket")
    for label in ("'Today'", "'Yesterday'", "'Last 7 days'", "'Older'"):
        assert label in buckets


def test_card_date_counts_calendar_days():
    """The card said "today" for a note edited at 18:00 yesterday, under the
    Yesterday heading. Count calendar days, as dateBucket does."""
    body = _function("relativeDate")
    assert "startOfDay(now) - startOfDay(d)" in body
    assert "now - d" not in body
