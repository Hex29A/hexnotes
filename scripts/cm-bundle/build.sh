#!/bin/sh
# Builds static/vendor/codemirror-<version>.min.js in a throwaway Node container.
# Pinned versions live in package.json next to this script.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
docker run --rm -v "$here":/src -v "$root/static/vendor":/out -w /tmp node:22-alpine sh -c '
  cp /src/package.json /src/entry.js . &&
  npm install --silent --no-audit --no-fund &&
  ver=$(node -p "JSON.parse(require(\"fs\").readFileSync(\"node_modules/@codemirror/view/package.json\")).version") &&
  npx esbuild entry.js --bundle --minify --format=iife --global-name=CM \
    --legal-comments=none --outfile=/out/codemirror-$ver.min.js &&
  chown '"$(id -u):$(id -g)"' /out/codemirror-$ver.min.js &&
  ls -l /out/codemirror-$ver.min.js'
