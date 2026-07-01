from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

try:
    import sounddevice as sd
    SD_AVAILABLE = True
except ImportError:
    sd = None
    SD_AVAILABLE = False

try:
    from funasr import AutoModel
    FUNASR_AVAILABLE = True
except ImportError:
    FUNASR_AVAILABLE = False


@dataclass
class RecordingResult:
    audio: np.ndarray
    sample_rate: int
    duration_ms: float


class AudioRecorder:
    """Microphone recorder with VAD-based endpoint detection.

    Records audio until silence is detected for a configurable duration.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        vad_model: str = "fsmn-vad",
        silence_ms: int = 800,
        device: Optional[int] = None,
    ):
        if not SD_AVAILABLE:
            raise ImportError("sounddevice not installed. Run: pip install sounddevice")
        self._sample_rate = sample_rate
        self._channels = channels
        self._silence_ms = silence_ms
        self._device = device
        self._vad_model = None
        self._vad_loaded = False

        # Recording state
        self._audio_buffer: list[np.ndarray] = []
        self._is_recording = False
        self._stop_event = threading.Event()
        self._stream: Optional[sd.InputStream] = None

        # VAD state
        self._silence_start: Optional[float] = None
        self._speech_detected = False

        if FUNASR_AVAILABLE:
            self._load_vad(vad_model)

    def _load_vad(self, model_name: str) -> None:
        if self._vad_loaded:
            return
        try:
            self._vad_model = AutoModel(model=model_name, device="cpu")
            self._vad_loaded = True
        except Exception as e:
            print(f"[Recorder] VAD load failed: {e}, using energy-based VAD")

    def _energy_vad(self, audio: np.ndarray, threshold: float = 0.02) -> bool:
        """Simple energy-based VAD fallback."""
        energy = np.sqrt(np.mean(audio ** 2))
        return energy > threshold

    def _check_vad(self, audio: np.ndarray) -> bool:
        """Check if audio chunk contains speech."""
        if self._vad_model is not None:
            try:
                res = self._vad_model.generate(input=audio)
                if res and len(res) > 0:
                    # VAD returns segments with speech
                    return len(res[0].get("text", "")) > 0 or res[0].get("value", "") != ""
            except Exception:
                pass
        return self._energy_vad(audio)

    def _audio_callback(self, indata: np.ndarray, frames: int,
                        time_info: dict, status) -> None:
        if self._stop_event.is_set():
            return

        chunk = indata.copy().flatten()
        self._audio_buffer.append(chunk)

        # VAD check
        is_speech = self._check_vad(chunk)
        current_time = time_info.get("currentTime", 0)

        if is_speech:
            self._speech_detected = True
            self._silence_start = None
        elif self._speech_detected:
            # Silence after speech
            if self._silence_start is None:
                self._silence_start = current_time
            elif (current_time - self._silence_start) * 1000 >= self._silence_ms:
                # Silence duration exceeded, stop recording
                self._stop_event.set()

    def record_until_silence(
        self,
        max_duration: float = 30.0,
        on_speech_start: Optional[Callable[[], None]] = None,
    ) -> RecordingResult:
        """Record audio until silence is detected.

        Args:
            max_duration: Maximum recording duration in seconds.
            on_speech_start: Callback when speech is first detected.

        Returns:
            RecordingResult with audio data and metadata.
        """
        self._audio_buffer.clear()
        self._stop_event.clear()
        self._is_recording = True
        self._silence_start = None
        self._speech_detected = False

        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=self._channels,
            dtype=np.float32,
            device=self._device,
            callback=self._audio_callback,
        )

        speech_callback_fired = False
        start_time = None

        with self._stream:
            start_time = sd.get_stream().time
            while not self._stop_event.is_set():
                sd.sleep(100)
                # Check max duration
                elapsed = sd.get_stream().time - start_time
                if elapsed >= max_duration:
                    self._stop_event.set()

                # Fire speech start callback
                if self._speech_detected and not speech_callback_fired:
                    speech_callback_fired = True
                    if on_speech_start:
                        on_speech_start()

        self._is_recording = False

        # Concatenate buffer
        if self._audio_buffer:
            audio = np.concatenate(self._audio_buffer)
        else:
            audio = np.array([], dtype=np.float32)

        duration_ms = len(audio) / self._sample_rate * 1000

        return RecordingResult(
            audio=audio,
            sample_rate=self._sample_rate,
            duration_ms=duration_ms,
        )

    def stop(self) -> None:
        """Stop current recording."""
        self._stop_event.set()
        self._is_recording = False


class AudioPlayer:
    """Audio playback queue with support for streaming chunks."""

    def __init__(
        self,
        sample_rate: int = 22050,
        buffer_size: int = 2,
    ):
        if not SD_AVAILABLE:
            raise ImportError("sounddevice not installed. Run: pip install sounddevice")
        self._sample_rate = sample_rate
        self._buffer_size = buffer_size
        self._queue: queue.Queue[Optional[tuple[np.ndarray, int]]] = queue.Queue()
        self._playing = False
        self._stop_event = threading.Event()
        self._play_thread: Optional[threading.Thread] = None

    def enqueue(self, audio: np.ndarray, sample_rate: Optional[int] = None) -> None:
        """Add audio chunk to playback queue."""
        sr = sample_rate or self._sample_rate
        self._queue.put((audio, sr))

    def start(self) -> None:
        """Start playback thread."""
        if self._playing:
            return
        self._playing = True
        self._stop_event.clear()
        self._play_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._play_thread.start()

    def stop(self) -> None:
        """Stop playback and clear queue."""
        self._stop_event.set()
        self._queue.put(None)  # Sentinel
        if self._play_thread:
            self._play_thread.join(timeout=2.0)
        self._playing = False
        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _playback_loop(self) -> None:
        """Background thread for audio playback."""
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.5)
                if item is None:
                    break
                audio, sr = item
                self._play_chunk(audio, sr)
            except queue.Empty:
                continue

    def _play_chunk(self, audio: np.ndarray, sample_rate: int) -> None:
        """Play a single audio chunk."""
        if len(audio) == 0:
            return
        # Resample if needed
        if sample_rate != self._sample_rate:
            import librosa
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=self._sample_rate)
        sd.play(audio, self._sample_rate)
        sd.wait()

    def wait_complete(self) -> None:
        """Wait for all queued audio to finish playing."""
        self._queue.put(None)
        if self._play_thread:
            self._play_thread.join()
        self._playing = False
