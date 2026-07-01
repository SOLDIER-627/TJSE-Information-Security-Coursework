from __future__ import annotations

from typing import AsyncGenerator, Generator, Optional

import numpy as np

from ..tts.base_tts import BaseTTS
from ..tts.cosyvoice_tts import CosyVoiceTTS
from ..utils.text_splitter import split_sentences


# TTS pronunciation dictionary for shipbuilding terms
_TTS_DICTIONARY: dict[str, str] = {
    "艏楼": "首楼",
    "艉轴": "尾轴",
    "艉封板": "尾封板",
    "艏柱": "首柱",
    "艉柱": "尾柱",
    "艏": "首",
    "艉": "尾",
    "舯": "船中",
    "舭": "舭部",
}


def normalize_tts_text(text: str) -> str:
    """Apply pronunciation normalization for TTS.

    1. Strip Markdown formatting (bold, italic, headings, list markers).
    2. Replace rare shipbuilding characters with common equivalents
       that TTS models can pronounce correctly.
    Longest matches applied first to avoid partial replacement.
    """
    import re
    # Strip Markdown bold/italic markers
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    # Strip Markdown headings (# ## ###)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Strip Markdown list markers (- * + followed by space)
    text = re.sub(r'^[\-\*\+]\s+', '', text, flags=re.MULTILINE)
    # Strip numbered list markers (1. 2. etc.)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    for old, new in sorted(_TTS_DICTIONARY.items(), key=lambda x: -len(x[0])):
        text = text.replace(old, new)
    return text


class StreamingTTS:
    """Sentence-level streaming TTS wrapper.

    Receives text from streaming LLM output, splits into sentences,
    and synthesizes each sentence independently for lower latency.
    """

    def __init__(self, tts: BaseTTS, normalize: bool = True):
        self._tts = tts
        self._normalize = normalize

    def synthesize_sentences(
        self,
        text: str,
        speaker_id: Optional[str] = None,
    ) -> Generator[tuple[np.ndarray, int], None, None]:
        """Split text into sentences and synthesize each one.

        Yields (audio, sample_rate) for each sentence.
        """
        sentences = split_sentences(text, min_length=2, split_on_clause=True)
        for sentence in sentences:
            if self._normalize:
                sentence = normalize_tts_text(sentence)
            audio, sr = self._tts.synthesize(sentence, speaker_id)
            yield audio, sr

    async def synthesize_streaming(
        self,
        text_stream: AsyncGenerator[str, None],
        speaker_id: Optional[str] = None,
        sentence_queue: Optional[object] = None,
    ) -> AsyncGenerator[tuple[np.ndarray, int], None, None]:
        """Accumulate streaming text, yield audio as sentences complete.

        This method consumes an async text stream (from LLM), detects
        sentence boundaries, and synthesizes each complete sentence.

        Args:
            text_stream: Async generator yielding text chunks from LLM.
            speaker_id: TTS speaker identity.
            sentence_queue: Optional asyncio.Queue for inter-task communication.

        Yields:
            (audio, sample_rate) for each synthesized sentence.
        """
        from ..utils.text_splitter import stream_sentences

        buffer = ""
        async for chunk in text_stream:
            buffer += chunk
            # Check for sentence boundaries
            while True:
                idx = -1
                for ending in ["。", "！", "？", "；", ".", "!", "?", ";"]:
                    pos = buffer.find(ending)
                    if pos != -1 and (idx == -1 or pos < idx):
                        idx = pos

                if idx != -1:
                    sentence = buffer[: idx + 1].strip()
                    buffer = buffer[idx + 1 :]

                    if sentence and len(sentence) >= 2:
                        if self._normalize:
                            sentence = normalize_tts_text(sentence)
                        audio, sr = self._tts.synthesize(sentence, speaker_id)
                        yield audio, sr
                else:
                    break

        # Process remaining buffer
        if buffer.strip() and len(buffer.strip()) >= 2:
            sentence = buffer.strip()
            if self._normalize:
                sentence = normalize_tts_text(sentence)
            audio, sr = self._tts.synthesize(sentence, speaker_id)
            yield audio, sr
