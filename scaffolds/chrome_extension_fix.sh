#!/usr/bin/env bash
# chrome_extension_fix.sh — generates 3 placeholder PNG icons missing from
# chrome-extension/public/. Without these, `npm run build` errors:
#   [crx:manifest-post] ENOENT: Could not load manifest asset "icon-16.png"
#
# Verified iter 46: build completes in 448ms after PNG addition.
# Operator can replace placeholders with branded icons later.

set -euo pipefail

SCAFFOLDS_DIR="$(cd "$(dirname "$0")" && pwd)"
PUBLIC_DIR="$SCAFFOLDS_DIR/chrome-extension/public"

if [ ! -f "$PUBLIC_DIR/manifest.json" ]; then
  echo "ERROR: $PUBLIC_DIR/manifest.json not found — run from ark/scaffolds/" >&2
  exit 1
fi

PUBLIC_DIR="$PUBLIC_DIR" python3 - <<'PYEOF'
import os, sys
try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow", file=sys.stderr)
    sys.exit(2)

public_dir = os.environ['PUBLIC_DIR']
color = (96, 64, 192, 255)  # accent #6040C0 placeholder
for size in (16, 48, 128):
    img = Image.new('RGBA', (size, size), color)
    out = os.path.join(public_dir, f'icon-{size}.png')
    img.save(out)
    print(f'  wrote {out} ({os.path.getsize(out)} bytes)')

print('done — chrome-extension is now buildable.')
PYEOF

echo
echo "Next: cd into chrome-extension and run \`npm install && npm run build\`"
echo "to verify (expected: 122 pkgs / 1s install + 448ms build)"
