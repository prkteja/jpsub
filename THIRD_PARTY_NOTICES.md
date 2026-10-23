# Third-party notices

jpsub's own code is under the MIT license (see `LICENSE`). It builds on the
following work.

## Downloaded on first run (not distributed with jpsub)

| Component | Source | License |
|---|---|---|
| JMdict Japanese–English dictionary | Electronic Dictionary Research and Development Group (EDRDG), via [jmdict-simplified](https://github.com/scriptin/jmdict-simplified) | [CC BY-SA 4.0](https://www.edrdg.org/edrdg/licence.html) |
| SenseVoice small speech model (ONNX export) | [FunAudioLLM/SenseVoice](https://github.com/FunAudioLLM/SenseVoice), converted by [sherpa-onnx](https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17) | [FunASR model license](https://github.com/modelscope/FunASR?tab=readme-ov-file#license) |
| Silero VAD | [snakers4/silero-vad](https://github.com/snakers4/silero-vad), via sherpa-onnx | MIT |

This publication has included material from the JMdict dictionary files in
accordance with the licence provisions of the Electronic Dictionaries Research
Group. See https://www.edrdg.org/edrdg/licence.html.

## Bundled in the binary

| Component | License |
|---|---|
| [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | Apache-2.0 |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) (shipped inside sherpa-onnx) | MIT |
| [SudachiPy](https://github.com/WorksApplications/sudachi.rs) and [SudachiDict](https://github.com/WorksApplications/SudachiDict) (core) | Apache-2.0 |
| [aiohttp](https://github.com/aio-libs/aiohttp) and its dependencies | Apache-2.0 / MIT |
| [NumPy](https://numpy.org) | BSD-3-Clause and others |
| [certifi](https://github.com/certifi/python-certifi) | MPL-2.0 |
| [CPython](https://www.python.org) | PSF License |
| [zlib](https://zlib.net) | zlib |
| [PyInstaller](https://pyinstaller.org) bootloader | GPL-2.0-or-later with the PyInstaller bootloader exception |

## Used from the system, not bundled

parec (PulseAudio/PipeWire), ffmpeg, GTK 3, gtk-layer-shell, WebKitGTK and
PyGObject.
