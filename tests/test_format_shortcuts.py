"""Formatting shortcuts in the editor (1.42), run in a real browser.

The transforms (mdToggleWrap, mdLink, mdToggleBullets, mdToggleCheckbox) are
called directly with page.evaluate; the key tests press the real keys in the
running app and check undo, autosave and the sidebar shortcut.

Needs Playwright and a Chromium/Chrome, which the Docker image does not ship,
so the module skips there. Run it locally:

    .venv/bin/pip install playwright
    .venv/bin/pytest tests/test_format_shortcuts.py -v
"""
import json
import socket
import threading
import time
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

TOKEN = "tok_browser_test"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    import uvicorn
    import backend.main as bm

    notes = tmp_path_factory.mktemp("notes")
    (notes / ".trash").mkdir()
    tokens = notes.parent / "tokens.json"
    entry = {"name": "browser", "token": TOKEN, "created_at": "2026-10-07T10:00:00"}
    tokens.write_text(json.dumps({"tokens": [entry]}))  # the app rereads this file
    saved = (bm.NOTES_PATH, bm.TRASH_PATH, bm.TOKENS_FILE, bm.TOKENS)
    bm.NOTES_PATH, bm.TRASH_PATH, bm.TOKENS_FILE = notes, notes / ".trash", tokens
    bm.TOKENS = [entry]
    bm.notes_index.clear()

    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(bm.app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", notes
    srv.should_exit = True
    t.join(5)
    bm.NOTES_PATH, bm.TRASH_PATH, bm.TOKENS_FILE, bm.TOKENS = saved


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            chrome = next((c for c in ("/usr/bin/google-chrome", "/usr/bin/chromium") if Path(c).exists()), None)
            if not chrome:
                pytest.skip("no Chromium for Playwright")
            b = p.chromium.launch(executable_path=chrome)
        yield b
        b.close()


@pytest.fixture
def page(server, browser):
    url, _ = server
    # The app CSP forbids eval, which wait_for_function polls with.
    ctx = browser.new_context(bypass_csp=True)
    # These drive the textarea directly, so they pin the classic editor; the
    # live (CodeMirror) editor is covered by test_live_editor.py.
    ctx.add_init_script(f"localStorage.setItem('hexnotes_token', '{TOKEN}');"
                        "localStorage.setItem('hexnotes_editor', 'classic');")
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url + "/")
    pg.wait_for_function("typeof mdToggleWrap === 'function'")
    # Let startup open the home note first, or it can land on top of the
    # note a test just created.
    pg.wait_for_function("activeNoteId === 'home' && isPreviewMode")
    yield pg
    ctx.close()
    assert not errors, errors


# --- pure transforms -------------------------------------------------------
# Each case: text with « and » marking the selection (or | for a caret), and
# the expected result marked the same way. Not [ ]: Markdown is full of those.

def _parse(marked):
    if "|" in marked:
        i = marked.index("|")
        return marked.replace("|", "", 1), i, i
    s = marked.index("«")
    e = marked.index("»") - 1
    return marked.replace("«", "", 1).replace("»", "", 1), s, e


def _mark(text, s, e):
    if s == e:
        return text[:s] + "|" + text[s:]
    return text[:s] + "«" + text[s:e] + "»" + text[e:]


def _run(page, fn, marked, *extra):
    text, s, e = _parse(marked)
    r = page.evaluate(f"([t, s, e, x]) => {fn}(t, s, e, ...x)", [text, s, e, list(extra)])
    if r is None:
        return None
    return _mark(r["text"], r["start"], r["end"])


WRAP_CASES = [
    # selection → wrap, selection on the content
    ("hello «world»", "**", "hello **«world»**"),
    ("«hello world»", "*", "*«hello world»*"),
    ("«gone»", "~~", "~~«gone»~~"),
    ("run «ls -la» now", "`", "run `«ls -la»` now"),
    # again → unwrap (markers outside the selection)
    ("hello **«world»**", "**", "hello «world»"),
    ("*«x»*", "*", "«x»"),
    ("~~«gone»~~", "~~", "«gone»"),
    # markers selected along with the text also unwrap
    ("«**world**»", "**", "«world»"),
    ("say «~~no~~» yes", "~~", "say «no» yes"),
    # whitespace at the selection edges stays outside the markers
    ("a« word »b", "**", "a **«word»** b"),
    # bold and italic share '*' and stay independent
    ("**«bold»**", "*", "***«bold»***"),
    ("***«both»***", "*", "**«both»**"),
    ("***«both»***", "**", "*«both»*"),
    ("*«it»*", "**", "***«it»***"),
    ("«**bold**»", "*", "***«bold»***"),
    # multi-line: each line on its own, list markers skipped
    ("«one\ntwo»", "**", "**«one**\n**two»**"),
    ("«- one\n- [ ] two\n\n1. three»", "**", "- **«one**\n- [ ] **two**\n\n1. **three»**"),
    ("«# Title\n> quote»", "*", "# *«Title*\n> *quote»*"),
    ("- **«one**\n- **two»**", "**", "- «one\n- two»"),
    # mixed: only the unwrapped line gets markers
    ("«**one**\ntwo»", "**", "**«one**\n**two»**"),
    # a selection starting mid-line is not pushed past a list marker
    ("- on«e\n- tw»o", "**", "- on**«e**\n- **tw»**o"),
    # caret inside a word: the word, caret kept in place
    ("hel|lo world", "**", "**hel|lo** world"),
    ("**hel|lo** world", "**", "hel|lo world"),
    ("e-po|st", "*", "*e-po|st*"),
    ("don't|", "*", "*don't|*"),
    ("smörgås|bord", "**", "**smörgås|bord**"),
    # caret at the end of a wrapped word steps over the closing marker
    ("**word|** after", "**", "**word**| after"),
    ("***word|***", "*", "***word*|**"),
    # caret on nothing: empty pair, and pressing again removes it
    ("a |", "**", "a **|**"),
    ("a **|**", "**", "a |"),
    ("|", "~~", "~~|~~"),
    ("x *|*", "*", "x |"),
    ("x **|**", "*", "x ***|***"),
]


@pytest.mark.parametrize("before,marker,after", WRAP_CASES)
def test_toggle_wrap(page, before, marker, after):
    assert _run(page, "mdToggleWrap", before, marker) == after


def test_wrap_then_unwrap_roundtrips(page):
    for marker in ("**", "*", "~~", "`"):
        for marked in ("a «b c» d", "«x\ny\nz»", "- «one\n- two»", "pre|fix", "|", "«å\n\nä»"):
            once = _run(page, "mdToggleWrap", marked, marker)
            assert _run(page, "mdToggleWrap", once, marker) == marked, (marker, marked, once)


def test_selection_of_only_whitespace_or_list_marker_does_nothing(page):
    assert _run(page, "mdToggleWrap", "«- »item", "**") is None
    assert _run(page, "mdToggleWrap", "a«   »b", "**") is None


LINK_CASES = [
    # selected text → [text](url) with "url" selected to type or paste over
    ("see «the docs» here", "see [the docs](«url») here"),
    ("wo|rd", "[word](«url»)"),
    # nothing → caret in the brackets
    ("a |", "a [|](url)"),
    # a selected URL becomes the target
    ("«https://29a.se/x»", "[|](https://29a.se/x)"),
    ("«www.29a.se»", "[|](www.29a.se)"),
]


@pytest.mark.parametrize("before,after", LINK_CASES)
def test_link(page, before, after):
    assert _run(page, "mdLink", before) == after


BULLET_CASES = [
    ("one|", "- one|"),
    ("«one\n\ntwo»", "«- one\n\n- two»"),
    ("«- one\n- two»", "«one\ntwo»"),
    ("«- one\ntwo»", "«- one\n- two»"),
    ("«1. one\n2. two»", "«- one\n- two»"),
    ("  ind|ented", "  - ind|ented"),
    ("- |x", "|x"),
    ("«- [ ] task\nplain»", "«- [ ] task\n- plain»"),
    ("first\nse|cond\nthird", "first\n- se|cond\nthird"),
    # a selection ending right after a newline leaves the next line alone
    ("«one\n»two", "«- one»\ntwo"),
]


@pytest.mark.parametrize("before,after", BULLET_CASES)
def test_bullets(page, before, after):
    assert _run(page, "mdToggleBullets", before) == after


CHECKBOX_CASES = [
    ("- [ ] mj|ölk", "- [x] mj|ölk"),
    ("- [x] mj|ölk", "- [ ] mj|ölk"),
    ("- [X] done|", "- [ ] done|"),
    ("  * [ ] nested|", "  * [x] nested|"),
    ("«- [x] a\n- [ ] b»", "«- [x] a\n- [x] b»"),
    ("«- [x] a\n- [x] b»", "«- [ ] a\n- [ ] b»"),
    ("bu|y milk", "- [ ] bu|y milk"),
    ("- bu|y milk", "- [ ] bu|y milk"),
    ("«a\n\nb»", "«- [ ] a\n\n- [ ] b»"),
]


@pytest.mark.parametrize("before,after", CHECKBOX_CASES)
def test_checkbox(page, before, after):
    assert _run(page, "mdToggleCheckbox", before) == after


# --- real keys in the app --------------------------------------------------

def _editor(page, content):
    page.evaluate("createNewNote()")
    ed = page.locator("#editor")
    ed.wait_for(state="visible")
    ed.click()
    ed.fill(content)
    return ed


def _sel(page, s, e):
    page.evaluate(f"$editor.setSelectionRange({s}, {e})")


def _state(page):
    return page.evaluate("[$editor.value, $editor.selectionStart, $editor.selectionEnd]")


def test_ctrl_b_bolds_and_ctrl_z_undoes(page):
    _editor(page, "hello world")
    _sel(page, 6, 11)
    page.keyboard.press("Control+b")
    assert _state(page) == ["hello **world**", 8, 13]
    page.keyboard.press("Control+b")
    assert _state(page)[0] == "hello world"
    page.keyboard.press("Control+z")
    assert _state(page)[0] == "hello **world**"
    page.keyboard.press("Control+z")
    assert _state(page)[0] == "hello world"


def test_ctrl_b_in_editor_does_not_toggle_sidebar(page):
    _editor(page, "x")
    before = page.evaluate("sidebarCollapsed")
    page.keyboard.press("Control+b")
    assert page.evaluate("sidebarCollapsed") == before


def test_sidebar_shortcuts(page):
    _editor(page, "x")
    before = page.evaluate("sidebarCollapsed")
    page.keyboard.press("Control+Shift+B")          # from the editor
    assert page.evaluate("sidebarCollapsed") != before
    assert _state(page)[0] == "x"
    page.evaluate("$editor.blur()")
    page.keyboard.press("Control+b")                # outside the editor
    assert page.evaluate("sidebarCollapsed") == before


def test_type_bold_then_leave_it(page):
    _editor(page, "")
    page.keyboard.press("Control+b")
    page.keyboard.type("bold")
    page.keyboard.press("Control+b")
    page.keyboard.type(" plain")
    assert _state(page)[0] == "**bold** plain"


def test_all_keys(page):
    _editor(page, "word")
    _sel(page, 0, 4)
    page.keyboard.press("Control+i")
    assert _state(page)[0] == "*word*"
    page.keyboard.press("Control+Shift+X")
    assert _state(page)[0] == "*~~word~~*"
    page.keyboard.press("Control+e")
    assert _state(page)[0] == "*~~`word`~~*"
    page.keyboard.press("Control+k")
    assert _state(page) == ["*~~`[word](url)`~~*", 11, 14]
    page.keyboard.type("https://x.se")
    assert _state(page)[0] == "*~~`[word](https://x.se)`~~*"

    page.locator("#editor").fill("task")
    page.keyboard.press("Control+Enter")
    assert _state(page)[0] == "- [ ] task"
    page.keyboard.press("Control+Enter")
    assert _state(page)[0] == "- [x] task"
    page.keyboard.press("Control+Enter")           # not continued as a new list item
    assert _state(page)[0] == "- [ ] task"

    page.locator("#editor").fill("item")
    page.keyboard.press("Control+Shift+Digit7")
    assert _state(page)[0] == "- item"


def test_formatting_autosaves(page, server):
    _, notes = server
    _editor(page, "save me")
    _sel(page, 0, 4)
    page.keyboard.press("Control+b")
    deadline = time.time() + 10
    while time.time() < deadline:
        if any("**save** me" in f.read_text() for f in notes.glob("*.md")):
            break
        time.sleep(0.2)
    else:
        pytest.fail("bold text never reached disk")


def test_altgr_combinations_are_left_alone(page):
    """AltGr arrives as Ctrl+Alt on Windows; AltGr+7 is { on Swedish keyboards."""
    _editor(page, "x")
    _sel(page, 0, 1)
    for combo in ("Control+Alt+b", "Control+Alt+i", "Control+Alt+Shift+Digit7"):
        page.keyboard.press(combo)
    assert _state(page)[0] == "x"


def test_multiline_bold_is_one_undo_step(page):
    _editor(page, "- one\n- two")
    _sel(page, 0, 11)
    page.keyboard.press("Control+b")
    assert _state(page)[0] == "- **one**\n- **two**"
    page.keyboard.press("Control+z")
    assert _state(page)[0] == "- one\n- two"


def test_ctrl_b_in_preview_toggles_sidebar(page):
    _editor(page, "# rendered")
    # Wait out the first autosave: it reopens the note under its new id.
    page.wait_for_function("!isNew && !isSaving && location.hash !== '#home'")
    page.evaluate("setPreviewMode(true)")
    before = page.evaluate("sidebarCollapsed")
    page.keyboard.press("Control+b")
    assert page.evaluate("sidebarCollapsed") != before
    page.evaluate("setPreviewMode(false)")
    assert _state(page)[0] == "# rendered"


def test_shortcuts_do_nothing_outside_the_editor(page):
    _editor(page, "keep")
    page.locator("#search-input").click()
    page.keyboard.press("Control+i")
    page.keyboard.press("Control+Enter")
    assert _state(page)[0] == "keep"
