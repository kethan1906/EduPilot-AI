import re

from config import CHUNK_OVERLAP, CHUNK_SIZE


def clean_text(text):
    """Collapse all whitespace runs (including PDF line breaks) to single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into word-based chunks; consecutive chunks share `overlap` words."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")

    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks
