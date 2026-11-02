"""Offline-only local token estimates; never discover/download provider tokenizers."""

import base64
import hashlib
import os
import tempfile
from functools import lru_cache
from pathlib import Path

import tiktoken

TOKENIZER_URL = "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
TOKENIZER_SHA = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"


@lru_cache(maxsize=1)
def local_encoding() -> tiktoken.Encoding | None:
    """Load verified local ranks directly, bypassing tiktoken's network loader."""
    directory = os.environ.get("TIKTOKEN_CACHE_DIR", os.environ.get("DATA_GYM_CACHE_DIR", str(Path(tempfile.gettempdir()) / "data-gym-cache")))
    if not directory:
        return None
    path = Path(directory) / hashlib.sha1(TOKENIZER_URL.encode()).hexdigest()
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if hashlib.sha256(raw).hexdigest() != TOKENIZER_SHA:
        return None
    ranks = {base64.b64decode(token): int(rank) for token, rank in (line.split() for line in raw.splitlines() if line)}
    # The pattern and special IDs belong to the pinned tiktoken cl100k_base format.
    return tiktoken.Encoding(
        name="cl100k_base",
        pat_str=r"'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| ?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s",
        mergeable_ranks=ranks,
        special_tokens={"<|endoftext|>": 100257, "<|fim_prefix|>": 100258, "<|fim_middle|>": 100259, "<|fim_suffix|>": 100260, "<|endofprompt|>": 100276},
    )


class TokenCounter:
    """Expose the estimation mode instead of claiming provider-exact usage."""

    def __init__(self) -> None:
        """Bind a cached offline tokenizer or a conservative byte-piece bound."""
        self.encoding = local_encoding()
        self.mode = "cl100k_base_estimate" if self.encoding else "utf8_piece_upper_bound"

    def count(self, text: str) -> int:
        """Estimate local tokens; the fallback bounds byte-level token pieces."""
        if self.encoding is not None:
            return len(self.encoding.encode(text, disallowed_special=()))
        return len(text.encode("utf-8"))
