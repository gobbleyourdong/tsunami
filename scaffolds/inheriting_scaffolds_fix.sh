#!/usr/bin/env bash
# inheriting_scaffolds_fix.sh — applies the verified iter-48/49 fix to
# both `auth-app` and `ai-app` scaffolds. Run from the repo root
# (ark/) with this script in scaffolds/.
#
# What it does (per scaffold):
#   1. Copies react-app/src/index.css → <scaffold>/src/index.css
#   2. Adds tailwindcss + @tailwindcss/vite to package.json devDependencies
#      (matching react-app's exact ^4.2.2 versions)
#   3. Replaces vite.config.ts to load tailwindcss/vite plugin
#
# Verified working in /tmp on iter 48 (auth-app: 240 pkgs, build 629ms)
# and iter 49 (ai-app: 184 pkgs, build 483ms).
#
# Idempotent: re-running on already-patched scaffold is a no-op (the
# package.json check + index.css comparison both confirm before edit).

set -euo pipefail

SCAFFOLDS_DIR="$(cd "$(dirname "$0")" && pwd)"
REACT_APP_CSS="$SCAFFOLDS_DIR/react-app/src/index.css"
REACT_APP_PKG="$SCAFFOLDS_DIR/react-app/package.json"

if [ ! -f "$REACT_APP_CSS" ]; then
  echo "ERROR: $REACT_APP_CSS not found — run from ark/scaffolds/" >&2
  exit 1
fi

# Pull react-app's exact tailwindcss versions so we don't drift
TAILWINDCSS_VER=$(node -e "console.log(JSON.parse(require('fs').readFileSync('$REACT_APP_PKG')).devDependencies.tailwindcss)")
TAILWINDCSS_VITE_VER=$(node -e "console.log(JSON.parse(require('fs').readFileSync('$REACT_APP_PKG')).devDependencies['@tailwindcss/vite'])")

apply_fix() {
  local scaffold="$1"
  local dir="$SCAFFOLDS_DIR/$scaffold"
  echo "→ patching $scaffold"

  # 1. Copy index.css (overwrite if present — it should match react-app)
  cp "$REACT_APP_CSS" "$dir/src/index.css"

  # 2. Add tailwindcss devDeps
  node -e "
    const fs = require('fs');
    const path = '$dir/package.json';
    const pkg = JSON.parse(fs.readFileSync(path, 'utf8'));
    pkg.devDependencies = pkg.devDependencies || {};
    pkg.devDependencies['tailwindcss'] = '$TAILWINDCSS_VER';
    pkg.devDependencies['@tailwindcss/vite'] = '$TAILWINDCSS_VITE_VER';
    fs.writeFileSync(path, JSON.stringify(pkg, null, 2) + '\n');
  "

  # 3. Replace vite.config.ts with tailwindcss-aware version
  cat > "$dir/vite.config.ts" <<'CFGEOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({ plugins: [react(), tailwindcss()] })
CFGEOF

  echo "  ✓ $scaffold: index.css copied, package.json updated, vite.config.ts replaced"
}

apply_fix "auth-app"
apply_fix "ai-app"

echo
echo "Done. Next: cd into each scaffold and run \`npm install && npm run build\`"
echo "to verify (expected: 240 pkgs / 3s install + 629ms build for auth-app)"
