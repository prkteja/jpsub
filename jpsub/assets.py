"""First-run download of the speech models and the dictionary.

Every file is pinned to a fixed release and checked against its SHA-256, so a
changed or corrupted download is rejected rather than used.
"""
import hashlib
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from . import paths

_SENSEVOICE = (
    "https://huggingface.co/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17"
    "/resolve/2365baeacb507f821a0c8120fcee3d484dba7a07"
)
_JMDICT_RELEASE = "3.6.2+20261005200550"


@dataclass(frozen=True)
class Asset:
    name: str
    url: str
    path: str  # relative to the data directory
    size: int
    sha256: str


MODELS = [
    Asset("SenseVoice speech recognition model", f"{_SENSEVOICE}/model.int8.onnx",
          "models/sensevoice/model.int8.onnx", 239_233_841,
          "c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51"),
    Asset("SenseVoice vocabulary", f"{_SENSEVOICE}/tokens.txt",
          "models/sensevoice/tokens.txt", 315_894,
          "f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc"),
    Asset("Silero voice activity detector",
          "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx",
          "models/silero_vad.onnx", 643_854,
          "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6"),
]
# Downloaded, converted into jmdict.sqlite, then deleted.
JMDICT = Asset(
    "JMdict Japanese-English dictionary",
    "https://github.com/scriptin/jmdict-simplified/releases/download/"
    f"{_JMDICT_RELEASE.replace('+', '%2B')}/jmdict-eng-{_JMDICT_RELEASE.replace('+', '%2B')}.json.zip",
    "downloads/jmdict-eng.json.zip", 11_528_608,
    "4601650cb900865cb9b388d6a045835120b90fbe451048d319bb8999635d596f",
)


def missing():
    """Assets that still need downloading."""
    root = paths.data_dir()
    needed = [a for a in MODELS if not (root / a.path).exists()]
    if not paths.dictionary_path().exists():
        needed.append(JMDICT)
    return needed


def _ssl_context():
    context = ssl.create_default_context()
    if not context.cert_store_stats()["x509_ca"]:
        # A packaged build may not find the system certificates; use the bundled set.
        try:
            import certifi

            context.load_verify_locations(certifi.where())
        except ImportError:
            pass
    return context


def _megabytes(size):
    return f"{size / 1e6:,.0f} MB" if size >= 1e6 else f"{size / 1e3:,.0f} kB"


def _download(asset, context):
    destination = paths.data_dir() / asset.path
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    for attempt in range(1, 7):
        have = partial.stat().st_size if partial.exists() else 0
        if have >= asset.size:
            break  # finished on an earlier attempt or run
        request = urllib.request.Request(asset.url, headers={"User-Agent": "jpsub"})
        if have:
            request.add_header("Range", f"bytes={have}-")
        try:
            with urllib.request.urlopen(request, timeout=30, context=context) as response:
                if have and response.status != 206:
                    have = 0  # the server ignored the resume request; start over
                with open(partial, "ab" if have else "wb") as out:
                    done = have
                    last = 0.0
                    while chunk := response.read(1 << 16):
                        out.write(chunk)
                        done += len(chunk)
                        if time.monotonic() - last > 0.2:
                            last = time.monotonic()
                            percent = 100 * done / asset.size
                            print(f"\r  {asset.name}: {percent:5.1f}% of {_megabytes(asset.size)}",
                                  end="", file=sys.stderr, flush=True)
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            print(f"\r  {asset.name}: interrupted ({error}); retrying ({attempt}/6)…",
                  file=sys.stderr)
            time.sleep(min(2 * attempt, 10))
    else:
        raise RuntimeError(f"could not download {asset.url}")

    digest = hashlib.sha256()
    with open(partial, "rb") as data:
        while chunk := data.read(1 << 20):
            digest.update(chunk)
    if digest.hexdigest() != asset.sha256:
        partial.unlink()
        raise RuntimeError(f"{asset.name} failed its checksum; the download was discarded")
    partial.replace(destination)
    print(f"\r  {asset.name}: done{' ' * 30}", file=sys.stderr)


def ensure(assume_yes=False):
    """Download whatever is missing, asking first. Returns False if declined."""
    needed = missing()
    if not needed:
        return True
    total = sum(a.size for a in needed)
    print("jpsub needs to download these files before it can run:\n", file=sys.stderr)
    for asset in needed:
        print(f"  {asset.name:<38} {_megabytes(asset.size):>8}", file=sys.stderr)
    print(f"\nTotal {_megabytes(total)}, saved to {paths.data_dir()}", file=sys.stderr)

    if not assume_yes:
        if not sys.stdin.isatty():
            print("Run jpsub in a terminal to confirm, or pass --yes.", file=sys.stderr)
            return False
        try:
            answer = input("Download now? [Y/n] ").strip().lower()
        except EOFError:
            answer = "n"
        if answer not in ("", "y", "yes"):
            print("Nothing downloaded.", file=sys.stderr)
            return False

    context = _ssl_context()
    for asset in needed:
        _download(asset, context)
    if JMDICT in needed:
        from .dictionary import build

        print("  Building the dictionary index (takes about half a minute)…", file=sys.stderr)
        archive = paths.data_dir() / JMDICT.path
        count = build(archive, paths.dictionary_path())
        archive.unlink()
        archive.parent.rmdir()
        print(f"  Dictionary ready: {count:,} entries", file=sys.stderr)
    print("All set.\n", file=sys.stderr)
    return True
