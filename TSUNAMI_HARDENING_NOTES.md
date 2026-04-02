# TSUNAMI hardening changes

This now replaces the original "best effort" installer with a usable in-repo hardened setup.

## What changed

1. `set +e` was replaced with `set -Eeuo pipefail`.
   The original script continued after network, build, and download failures. The hardened version stops on the first integrity or build failure.

2. `curl | bash` was removed.
   The original auto-installed `fnm` by piping a remote script into `bash`. The hardened version never executes remote shell scripts.

3. Mutable repo bootstrapping was removed.
   The original cloned `tsunami` and `llama.cpp` from whatever default branch was current. The hardened path now runs from a checked-out repo and pins `llama.cpp` to a repo-selected ref unless you override `LLAMA_CPP_REF`.

4. Hugging Face downloads now require a manifest with exact revisions and SHA-256 checksums.
   The original used `/resolve/main/...` with only a size check. The hardened version uses `models/model-manifest.lock` and refuses downloads unless each entry supplies a pinned revision and checksum.

   The manifest format is `repo|revision|remote_filename|local_filename|sha256`. It rejects obvious mutable revisions such as `main`, `master`, and `HEAD`, and validates that each checksum looks like a 64-character SHA-256 value before download.

5. Python installs are isolated into a virtualenv.
   The original attempted `pip3 install`, `--break-system-packages`, and `--user`. The hardened version uses `python3 -m venv`, installs from repo-shipped `requirements.lock`, and the launcher now prefers `./.venv/bin/python`.

6. Node installs are no longer automatic.
   The original tried to install Node itself. The hardened version only uses existing `node`, installs the CLI with `npm ci` from tracked `cli/package-lock.json`, and only falls back to mutable npm installs if you explicitly opt into `ALLOW_UNPINNED_NPM=1`.

7. Shell persistence is opt-in.
   The original appended aliases and `PATH` changes to the first shell rc file it found. The hardened version does this only when `INSTALL_SHELL_ALIAS=1`.

8. Output suppression was reduced.
   The original redirected many operations to `/dev/null`. The hardened version keeps command failures visible so you can audit what happened.

## What is still missing

- optional diffusion/image-generation extras, if you want those bundled into setup too
- the legacy `tsu update` path, if you want runtime updates to be ref-pinned too

The core local setup path is now pinned and verified, including browser automation for the built-in screenshot and browser tools.

## Example usage

```bash
git clone https://github.com/gobbleyourdong/tsunami.git
cd tsunami
./setup.sh
./tsu
```

To override the bundled defaults:

```bash
LLAMA_CPP_REF=b8611 MODEL_MANIFEST="$PWD/models/model-manifest.lock" ./setup.sh
```
