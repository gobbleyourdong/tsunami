"""Chat-template injection defense.

QA-3 Fire 38: a literal `<end_of_turn><start_of_turn>system\\n...` string in
user input was tokenized as real role boundaries, letting adversaries inject
a fake system message with arbitrary instructions. Inserting a zero-width
space after the opening `<` breaks the exact-string lookup the tokenizer
does for special tokens (they're resolved as whole literals, not via
subword merges) while leaving the text visually identical in logs and
downstream rendering.

Applied to user + tool roles in serve_transformers.py. Assistant messages
emit real special tokens from the model — escaping those would break
tool-call parsing.
"""

from __future__ import annotations

_ZWSP = "\u200b"
_GEMMA_ROLE_TOKENS = ("<start_of_turn>", "<end_of_turn>")


def escape_role_tokens(text):
    """Neutralize Gemma role markers inside adversary-controllable content."""
    if not isinstance(text, str) or "<" not in text:
        return text
    for tok in _GEMMA_ROLE_TOKENS:
        if tok in text:
            text = text.replace(tok, "<" + _ZWSP + tok[1:])
    return text
