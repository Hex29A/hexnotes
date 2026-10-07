// Entry for the vendored CodeMirror 6 bundle (static/vendor/codemirror-*.min.js).
// Exposes the pieces the live-preview editor in index.html uses as window.CM.
// Rebuild with scripts/cm-bundle/build.sh — the app itself has no build step.
export { EditorState, EditorSelection, Prec } from '@codemirror/state';
export { EditorView, ViewPlugin, Decoration, WidgetType, keymap } from '@codemirror/view';
export { history, defaultKeymap, historyKeymap } from '@codemirror/commands';
export { syntaxTree, syntaxHighlighting, HighlightStyle, Language, defineLanguageFacet } from '@codemirror/language';
// @lezer/markdown directly rather than @codemirror/lang-markdown, which pulls in
// the HTML, CSS and JavaScript languages for embedded code (~300 kB).
export { parser as markdownParser, GFM } from '@lezer/markdown';
export { tags } from '@lezer/highlight';
