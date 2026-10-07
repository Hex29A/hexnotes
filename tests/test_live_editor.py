"""Live-preview editor (CodeMirror 6), run in a real browser.

The live view renders markdown in place while the saved text stays plain
markdown; the textarea is the source mode. These check that the rendering
hides the right marks, that edits made in the live view reach the textarea
model and autosave, and that the app's own handlers (format keys, list
continuation, [[ suggestions, wiki navigation) still run through it.

Needs Playwright and Chromium/Chrome, like test_format_shortcuts.py.
"""
import time

import pytest

import backend.main as bm

sync_api = pytest.importorskip("playwright.sync_api")

from tests.test_format_shortcuts import TOKEN, browser, server  # noqa: E402,F401

DEMO = """# Heading

Some **bold**, *italic*, ~~gone~~ and `code`. A [link](https://example.com), [[home]] and [[missing]].

- [ ] milk
- [x] bread
- plain item

> a quote

```
**not bold** in code
```
"""


@pytest.fixture
def page(server, browser):
    url, notes = server
    (notes / "home.md").write_text("# Home\n")
    (notes / "demo.md").write_text(DEMO)
    bm.build_index()
    ctx = browser.new_context()
    ctx.add_init_script(f"localStorage.setItem('hexnotes_token', '{TOKEN}');"
                        "localStorage.removeItem('hexnotes_editor');")
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
    pg.goto(url + "/#demo")
    _wait(pg, "typeof LIVE !== 'undefined' && activeNoteId === 'demo' && liveShown")
    yield pg, notes
    ctx.close()
    assert not errors, errors


def _wait(pg, expr, timeout=5):
    # wait_for_function polls with eval, which the app CSP forbids
    end = time.time() + timeout
    while time.time() < end:
        if pg.evaluate(expr):
            return
        time.sleep(0.05)
    raise AssertionError("timed out waiting for: " + expr)


def _visible_text(pg):
    return pg.evaluate("liveView.contentDOM.innerText")


def test_opens_in_live_view_with_marks_hidden(page):
    pg, _ = page
    text = _visible_text(pg)
    assert "Heading" in text and "# Heading" not in text
    assert "bold" in text and "**bold**" not in text
    assert "link" in text and "https://example.com" not in text
    assert "home" in text and "[[home]]" not in text
    assert "**not bold** in code" in text          # code is left alone
    assert pg.locator(".cm-lp-task").count() == 2
    assert pg.locator(".cm-lp-wiki-missing", has_text="missing").count() == 1


def test_checkbox_click_ticks_and_saves(page):
    pg, notes = page
    pg.locator(".cm-lp-task").first.click()
    _wait(pg, "$editor.value.includes('- [x] milk')")
    _wait(pg, "pendingContent === null && !isSaving")
    assert "- [x] milk" in (notes / "demo.md").read_text()


def test_typing_autosaves_and_format_key_works(page):
    pg, notes = page
    pg.locator(".cm-content").click()
    pg.keyboard.press("Control+End")
    pg.keyboard.type("åäö ")
    pg.keyboard.press("Control+b")
    pg.keyboard.type("x")
    _wait(pg, "$editor.value.endsWith('åäö **x**')")
    assert not pg.evaluate("sidebarCollapsed")      # Ctrl+B is bold here
    _wait(pg, "pendingContent === null && !isSaving", timeout=4)
    assert (notes / "demo.md").read_text().endswith("åäö **x**")


def test_list_continues_and_undo_works(page):
    pg, _ = page
    pg.locator(".cm-content").click()
    pg.keyboard.press("Control+End")
    pg.keyboard.type("- a")
    pg.keyboard.press("Enter")
    pg.keyboard.type("b")
    assert pg.evaluate("$editor.value").endswith("- a\n- b")
    pg.keyboard.press("Control+z")
    assert not pg.evaluate("$editor.value").endswith("- b")


def test_source_toggle_keeps_text_in_sync(page):
    pg, _ = page
    pg.locator(".cm-content").click()
    pg.keyboard.press("Control+m")
    assert pg.evaluate("!liveShown && getComputedStyle($editor).display !== 'none'")
    pg.keyboard.press("Control+End")
    pg.keyboard.type("Z")
    pg.keyboard.press("Control+m")
    assert pg.evaluate("liveShown && liveView.state.doc.toString() === $editor.value")
    assert pg.evaluate("$editor.value").endswith("Z")


def test_wiki_suggestion_and_navigation(page):
    pg, _ = page
    pg.locator(".cm-content").click()
    pg.keyboard.press("Control+End")
    pg.keyboard.type("[[ho")
    _wait(pg, "$wlSuggest.style.display === 'block'")
    pg.keyboard.press("Enter")
    assert pg.evaluate("$editor.value").endswith("[[home]]")
    pg.keyboard.press("Control+Home")
    pg.locator(".cm-lp-wiki", has_text="home").first.click()
    _wait(pg, "activeNoteId === 'home'")


def test_undo_does_not_cross_notes(page):
    pg, _ = page
    pg.locator(".cm-content").click()
    pg.keyboard.press("Control+End")
    pg.keyboard.type("Q")
    pg.evaluate("openNote('home')")
    _wait(pg, "activeNoteId === 'home'")
    pg.locator(".cm-content").click()
    pg.keyboard.press("Control+z")
    assert pg.evaluate("$editor.value") == "# Home\n"


def test_classic_switch(server, browser):
    url, notes = server
    (notes / "demo.md").write_text(DEMO)
    bm.build_index()
    ctx = browser.new_context()
    ctx.add_init_script(f"localStorage.setItem('hexnotes_token', '{TOKEN}');")
    pg = ctx.new_page()
    pg.goto(url + "/?editor=classic#demo")
    _wait(pg, "typeof LIVE !== 'undefined' && activeNoteId === 'demo'")
    assert pg.evaluate("LIVE") is False
    assert pg.evaluate("localStorage.getItem('hexnotes_editor')") == "classic"
    assert pg.locator(".cm-editor").count() == 0
    ctx.close()
