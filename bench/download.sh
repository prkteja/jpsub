#!/bin/bash
# Fetch the comparison models and the FLEURS Japanese dev set (resumable).
cd "$(dirname "$0")"
get() { # url dest
  mkdir -p "$(dirname "$2")"
  for i in 1 2 3 4 5 6; do
    curl -sSL -C - --speed-limit 20000 --speed-time 30 -o "$2" "$1" && return 0
    sleep 2
  done
  echo "FAILED $1"; return 1
}
HF=https://huggingface.co
get $HF/datasets/google/fleurs/resolve/main/data/ja_jp/dev.tsv data/dev.tsv
get $HF/datasets/google/fleurs/resolve/main/data/ja_jp/audio/dev.tar.gz data/dev.tar.gz
R=reazon-research/reazonspeech-k2-v2
for f in tokens.txt encoder-epoch-99-avg-1.int8.onnx decoder-epoch-99-avg-1.onnx joiner-epoch-99-avg-1.int8.onnx; do get $HF/$R/resolve/main/$f models/reazonspeech/$f; done
# SenseVoice is shared with the app: run jpsub once (or `jpsub --setup`) to fetch it.
for f in config.json model.bin tokenizer.json; do get $HF/Systran/faster-whisper-small/resolve/main/$f models/whisper-small/$f; done
get $HF/Systran/faster-whisper-small/resolve/main/vocabulary.txt models/whisper-small/vocabulary.txt
for f in config.json model.bin tokenizer.json vocabulary.json preprocessor_config.json; do get $HF/kotoba-tech/kotoba-whisper-v2.0-faster/resolve/main/$f models/kotoba-v2/$f; done
for f in config.json model.bin tokenizer.json vocabulary.json preprocessor_config.json; do get $HF/deepdml/faster-whisper-large-v3-turbo-ct2/resolve/main/$f models/turbo/$f; done
echo DONE; du -sh models/* data/*
