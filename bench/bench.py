"""Benchmark local Japanese speech-to-text models on FLEURS ja_jp dev clips.

Reports character error rate (CER), real-time factor (RTF = compute time /
audio time, lower is faster) and per-clip latency.

Usage: bench.py MODEL [N_CLIPS] [THREADS] [BEAM]
MODEL is sensevoice, reazonspeech, whisper-small, kotoba-v2 or turbo.
Run download.sh first, and install requirements.txt from this folder.
"""
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf
from rapidfuzz.distance import Levenshtein

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))  # for jpsub.paths
MODELS = ROOT / "models"
DATA = ROOT / "data"


def normalize(text):
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"[\s\W_]+", "", text)


def load_clips(n):
    clips = []
    for line in (DATA / "dev.tsv").read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        wav = DATA / "dev" / cols[1]
        if wav.exists():
            clips.append((wav, cols[2]))
    # Evenly spaced sample so every model sees the same clips.
    step = max(1, len(clips) // n)
    return clips[::step][:n]


def make_whisper(name, threads, beam):
    from faster_whisper import WhisperModel

    model = WhisperModel(str(MODELS / name), device="cpu", compute_type="int8", cpu_threads=threads)

    def run(audio):
        segments, _ = model.transcribe(
            audio, language="ja", beam_size=beam, condition_on_previous_text=False
        )
        return "".join(s.text for s in segments)

    return run


def make_sherpa(name, threads):
    import sherpa_onnx

    if name == "sensevoice":
        # Shared with the app, which downloads it on first run.
        from jpsub.paths import models_dir

        d = models_dir() / name
    else:
        d = MODELS / name
    if name == "reazonspeech":
        rec = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(d / "encoder-epoch-99-avg-1.int8.onnx"),
            decoder=str(d / "decoder-epoch-99-avg-1.onnx"),
            joiner=str(d / "joiner-epoch-99-avg-1.int8.onnx"),
            tokens=str(d / "tokens.txt"),
            num_threads=threads,
        )
    else:
        rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(d / "model.int8.onnx"),
            tokens=str(d / "tokens.txt"),
            num_threads=threads,
            language="ja",
            use_itn=True,
        )

    def run(audio):
        stream = rec.create_stream()
        stream.accept_waveform(16000, audio)
        rec.decode_stream(stream)
        return stream.result.text

    return run


def main():
    name = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    threads = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    beam = int(sys.argv[4]) if len(sys.argv) > 4 else 1

    t0 = time.perf_counter()
    if name in ("reazonspeech", "sensevoice"):
        run = make_sherpa(name, threads)
    else:
        run = make_whisper(name, threads, beam)
    load_s = time.perf_counter() - t0

    clips = load_clips(n)
    audio0, _ = sf.read(clips[0][0], dtype="float32")
    run(audio0)  # warm-up

    errors = chars = 0
    audio_s = compute_s = 0.0
    latencies = []
    samples = []
    for wav, ref in clips:
        audio, sr = sf.read(wav, dtype="float32")
        assert sr == 16000, sr
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        t = time.perf_counter()
        hyp = run(np.ascontiguousarray(audio))
        dt = time.perf_counter() - t
        r, h = normalize(ref), normalize(hyp)
        errors += Levenshtein.distance(r, h)
        chars += len(r)
        audio_s += len(audio) / sr
        compute_s += dt
        latencies.append(dt)
        if len(samples) < 3:
            samples.append({"ref": ref, "hyp": hyp})

    print(json.dumps({
        "model": name,
        "threads": threads,
        "beam": beam,
        "clips": len(clips),
        "avg_clip_s": round(audio_s / len(clips), 1),
        "cer_pct": round(100 * errors / chars, 1),
        "rtf": round(compute_s / audio_s, 3),
        "latency_median_s": round(float(np.median(latencies)), 2),
        "latency_p90_s": round(float(np.percentile(latencies, 90)), 2),
        "load_s": round(load_s, 1),
        "samples": samples,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
