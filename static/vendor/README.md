# Vendored third-party libraries

Served locally instead of from a CDN. A CDN-hosted `purify.min.js` can be swapped
out by whoever controls the CDN, which would both disable the XSS sanitizer and
expose the API token in `localStorage` — so these are pinned and committed.
The webfont is vendored for the same reason plus one more: Google Fonts serves
whatever build is current, so the rendered weight can drift under us with no
commit to point at — pinning a version file keeps it stable.

| File | Package | Version | License | SHA-256 |
|------|---------|---------|---------|---------|
| `marked-15.0.12.min.js` | [marked](https://github.com/markedjs/marked) | 15.0.12 | MIT | `3e7e7d7feb3e5d58cb6c804f68ab5c24cc7e5eb6270fd6e5cbb9124739217d0c` |
| `purify-3.4.15.min.js` | [DOMPurify](https://github.com/cure53/DOMPurify) | 3.4.15 | Apache-2.0 / MPL-2.0 | `f263b05369e050fa175d4ecb9c9358eb4253602d510297adfb31df48b2f1c4d5` |
| `JetBrainsMono-2.304-Regular.woff2` | [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono) | 2.304 | OFL-1.1 | `a9cb1cd82332b23a47e3a1239d25d13c86d16c4220695e34b243effa999f45f2` |
| `JetBrainsMono-2.304-Bold.woff2` | [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono) | 2.304 | OFL-1.1 | `c503cc5ec5f8b2c7666b7ecda1adf44bd45f2e6579b2eba0fc292150416588a2` |

marked/purify hashes were verified identical when downloaded from jsDelivr and
unpkg. The font files came straight from the project's own GitHub release
(`fonts/webfonts/` in the release zip), so there's no second CDN to cross-check
against — the release asset itself is the source of truth.

## Upgrading

```bash
curl -sfL -o static/vendor/marked-<ver>.min.js https://cdn.jsdelivr.net/npm/marked@<ver>/marked.min.js
sha256sum static/vendor/marked-<ver>.min.js   # compare against unpkg.com
```

Then update the `<script src>` in `static/index.html`, the `STATIC` list plus the
`CACHE` name in `static/sw.js`, and this table.
