from __future__ import annotations

import re
from typing import Generator


# Sentence-ending punctuation for Chinese and English
_SENTENCE_ENDINGS = re.compile(r'([。！？；\.\!\?;])')

# Chinese comma / enumeration — can optionally split long segments
_CLAUSE_ENDINGS = re.compile(r'([，,、])')


def split_sentences(
    text: str,
    min_length: int = 2,
    max_length: int = 200,
    split_on_clause: bool = False,
) -> list[str]:
    """Split text into sentences at punctuation boundaries.

    Args:
        text: Input text to split.
        min_length: Minimum character length for a sentence segment.
        max_length: If a segment exceeds this, force-split on clause boundaries.
        split_on_clause: Also split on commas/clauses (for streaming TTS).

    Returns:
        List of sentence strings.
    """
    if not text or not text.strip():
        return []

    # Primary split on sentence endings
    parts = _SENTENCE_ENDINGS.split(text)

    # Re-attach punctuation to the preceding segment
    segments: list[str] = []
    i = 0
    while i < len(parts):
        seg = parts[i]
        # If next part is punctuation, attach it
        if i + 1 < len(parts) and _SENTENCE_ENDINGS.match(parts[i + 1]):
            seg += parts[i + 1]
            i += 2
        else:
            i += 1
        seg = seg.strip()
        if seg:
            segments.append(seg)

    # Merge short segments
    merged: list[str] = []
    buffer = ""
    for seg in segments:
        buffer = (buffer + seg).strip()
        if len(buffer) >= min_length:
            if len(buffer) > max_length and split_on_clause:
                # Force split on clause boundaries
                sub_parts = _CLAUSE_ENDINGS.split(buffer)
                sub_buf = ""
                for sp in sub_parts:
                    sub_buf += sp
                    if len(sub_buf) >= min_length and (
                        _CLAUSE_ENDINGS.match(sp) or len(sub_buf) >= max_length
                    ):
                        merged.append(sub_buf.strip())
                        sub_buf = ""
                if sub_buf.strip():
                    merged.append(sub_buf.strip())
                buffer = ""
            else:
                merged.append(buffer)
                buffer = ""
    if buffer.strip():
        merged.append(buffer.strip())

    return merged


def stream_sentences(
    text_stream: Generator[str, None, None],
    min_length: int = 2,
    max_length: int = 200,
) -> Generator[str, None, None]:
    """Accumulate streaming text and yield complete sentences.

    Receives text chunks from LLM streaming output, yields sentences
    as soon as they are complete (ending punctuation reached).
    """
    buffer = ""
    for chunk in text_stream:
        buffer += chunk
        # Check if buffer contains sentence-ending punctuation
        while True:
            match = _SENTENCE_ENDINGS.search(buffer)
            if match:
                end_pos = match.end()
                sentence = buffer[:end_pos].strip()
                if len(sentence) >= min_length:
                    yield sentence
                buffer = buffer[end_pos:]
            else:
                break
    # Yield remaining buffer as last sentence
    if buffer.strip() and len(buffer.strip()) >= min_length:
        yield buffer.strip()
