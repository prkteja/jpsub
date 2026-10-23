"""Audio capture, voice activity detection and speech recognition."""
import re
import subprocess
import threading
import time
import numpy as np
import sherpa_onnx

from . import paths

SAMPLE_RATE = 16000
CHUNK_SAMPLES = SAMPLE_RATE // 10
PARTIAL_INTERVAL = 0.4  # seconds between provisional results while someone is speaking
_HAS_CONTENT = re.compile(r"\w")
# The model sometimes puts spaces between Japanese words; keep only those between Latin words.
_STRAY_SPACE = re.compile(r"(?<![A-Za-z0-9])\s+|\s+(?![A-Za-z0-9])")


def capture_command(source=None, file=None):
    if file:
        # -re paces decoding at playback speed so a file behaves like live audio.
        return ["ffmpeg", "-v", "error", "-re", "-i", file,
                "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"]
    return ["parec", f"--device={source or '@DEFAULT_MONITOR@'}", "--format=s16le",
            f"--rate={SAMPLE_RATE}", "--channels=1", "--latency-msec=100",
            "--client-name=jpsub"]


class Recognizer(threading.Thread):
    """Reads audio from a capture process and emits subtitle events.

    Events passed to `emit`:
      {"type": "partial", "id", "text"}  provisional text for the line being spoken
      {"type": "final", "id", "text"}    the finished line
      {"type": "status", "state", "detail"}
    """

    def __init__(self, emit, source=None, file=None, threads=2):
        super().__init__(daemon=True)
        self.emit = emit
        self.paused = threading.Event()
        self._command = capture_command(source, file)
        self._once = bool(file)
        self._process = None
        self._stopping = False
        self._next_id = 1

        models = paths.models_dir()
        self._asr = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(models / "sensevoice" / "model.int8.onnx"),
            tokens=str(models / "sensevoice" / "tokens.txt"),
            num_threads=threads,
            language="ja",
            use_itn=True,
        )
        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(models / "silero_vad.onnx")
        config.silero_vad.threshold = 0.5
        config.silero_vad.min_silence_duration = 0.35
        config.silero_vad.min_speech_duration = 0.25
        config.silero_vad.max_speech_duration = 8
        config.sample_rate = SAMPLE_RATE
        self._window = config.silero_vad.window_size
        self._vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=60)

    def stop(self):
        self._stopping = True
        if self._process:
            self._process.terminate()

    def run(self):
        while not self._stopping:
            try:
                self._process = subprocess.Popen(
                    self._command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
            except FileNotFoundError:
                self.emit({"type": "status", "state": "error",
                           "detail": f"{self._command[0]} is not installed"})
                return
            self.emit({"type": "status", "state": "listening", "detail": ""})
            self._listen(self._process.stdout)
            error = self._process.stderr.read().decode(errors="replace").strip()
            self._process.wait()
            if self._stopping:
                return
            if self._once:
                self.emit({"type": "status", "state": "ended", "detail": error})
                return
            self.emit({"type": "status", "state": "error",
                       "detail": error or "Audio capture stopped; retrying"})
            time.sleep(2)

    def _transcribe(self, samples):
        stream = self._asr.create_stream()
        stream.accept_waveform(SAMPLE_RATE, samples)
        self._asr.decode_stream(stream)
        text = _STRAY_SPACE.sub("", stream.result.text.strip())
        return text if _HAS_CONTENT.search(text) else ""

    def _listen(self, pipe):
        empty = np.zeros(0, dtype=np.float32)
        buffer, offset = empty, 0
        speaking = False
        last_partial = 0.0
        while True:
            raw = pipe.read(CHUNK_SAMPLES * 2)
            if not raw:
                # End of a file: emit whatever speech was still in progress.
                self._vad.flush()
                self._drain()
                return
            if self.paused.is_set():
                self._vad.reset()
                buffer, offset, speaking = empty, 0, False
                continue
            chunk = np.frombuffer(raw[: len(raw) // 2 * 2], dtype=np.int16)
            buffer = np.concatenate([buffer, chunk.astype(np.float32) / 32768])

            while offset + self._window < len(buffer):
                self._vad.accept_waveform(buffer[offset : offset + self._window])
                if not speaking and self._vad.is_speech_detected():
                    speaking = True
                    last_partial = time.monotonic()
                offset += self._window

            if not speaking:
                # Keep a short lead-in so the start of the next phrase is not clipped.
                keep = 10 * self._window
                if len(buffer) > keep:
                    offset -= len(buffer) - keep
                    buffer = buffer[-keep:]
            elif time.monotonic() - last_partial > PARTIAL_INTERVAL:
                text = self._transcribe(buffer)
                if text:
                    self.emit({"type": "partial", "id": self._next_id, "text": text})
                last_partial = time.monotonic()

            if self._drain():
                buffer, offset, speaking = empty, 0, False

    def _drain(self):
        """Emit every phrase the voice detector has finished; return whether any were."""
        finished = False
        while not self._vad.empty():
            text = self._transcribe(self._vad.front.samples)
            self._vad.pop()
            if text:
                self.emit({"type": "final", "id": self._next_id, "text": text})
                self._next_id += 1
            else:
                self.emit({"type": "partial", "id": self._next_id, "text": ""})
            finished = True
        return finished
