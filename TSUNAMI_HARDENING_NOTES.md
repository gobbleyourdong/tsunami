# TSUNAMI hardening changes

This replaces the original "best effort" installer with a fail-closed template.

## What changed

1. `set +e` was replaced with `set -Eeuo pipefail`.
   The original script continued after network, build, and download failures. The hardened version stops on the first integrity or build failure.

2. `curl | bash` was removed.
   The original auto-installed `fnm` by piping a remote script into `bash`. The hardened version never executes remote shell scripts.

3. Mutable Git refs were removed.
   The original cloned `tsunami` and `llama.cpp` from whatever default branch was current. The hardened version requires `TSUNAMI_REPO_REF` and `LLAMA_CPP_REF` and checks out those exact refs.

4. Hugging Face downloads now require a manifest with exact revisions and SHA-256 checksums.
   The original used `/resolve/main/...` with only a size check. The hardened version refuses all model downloads unless you provide `repo|revision|filename|sha256`.

   It also rejects obvious mutable revisions such as `main`, `master`, and `HEAD`, and validates that each checksum looks like a 64-character SHA-256 value before download.

5. Python installs are isolated into a virtualenv.
   The original attempted `pip3 install`, `--break-system-packages`, and `--user`. The hardened version uses `python3 -m venv` and refuses mutable dependency installs unless you explicitly opt into `ALLOW_UNPINNED_DEPS=1`.

6. Node installs are no longer automatic.
   The original tried to install Node itself. The hardened version only uses existing `node` and runs `npm ci` only if `package-lock.json` exists.

7. Shell persistence is opt-in.
   The original appended aliases and `PATH` changes to the first shell rc file it found. The hardened version does this only when `INSTALL_SHELL_ALIAS=1`.

8. Output suppression was reduced.
   The original redirected many operations to `/dev/null`. The hardened version keeps command failures visible so you can audit what happened.

## What is still missing

- Real pinned refs for `tsunami` and `llama.cpp`
- Real SHA-256 values for each model file
- Ideally, a repo-provided `requirements.lock` or equivalent hashed lockfile

Without those three inputs, I would still not run the installer.

## Example usage

```bash
cat > /tmp/tsunami-model-manifest.txt <<'EOF'
unsloth/Qwen3.5-2B-GGUF|<hf-revision>|Qwen3.5-2B-Q4_K_M.gguf|<sha256>
unsloth/Qwen3.5-2B-GGUF|<hf-revision>|mmproj-2B-BF16.gguf|<sha256>
unsloth/Qwen3.5-9B-GGUF|<hf-revision>|Qwen3.5-9B-Q4_K_M.gguf|<sha256>
unsloth/Qwen3.5-9B-GGUF|<hf-revision>|mmproj-9B-BF16.gguf|<sha256>
unsloth/Qwen3.5-27B-GGUF|<hf-revision>|Qwen3.5-27B-Q8_0.gguf|<sha256>
unsloth/Qwen3.5-27B-GGUF|<hf-revision>|mmproj-27B-BF16.gguf|<sha256>
EOF

export TSUNAMI_REPO_REF="<pinned ref>"
export LLAMA_CPP_REF="<pinned ref>"
export MODEL_MANIFEST="/tmp/tsunami-model-manifest.txt"

bash /tmp/tsunami_setup_hardened.sh
```
