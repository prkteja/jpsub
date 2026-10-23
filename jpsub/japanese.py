"""Split Japanese text into clickable words with furigana and dictionary forms."""
import re

from sudachipy import dictionary, tokenizer

KANJI = r"㐀-䶿一-鿿豈-﫿々〆ヶ"
_HAS_KANJI = re.compile(f"[{KANJI}]")
_RUNS = re.compile(f"[{KANJI}]+|[^{KANJI}]+")
_HAS_JAPANESE = re.compile(f"[{KANJI}\\u3040-\\u30ff]")
_KATA_TO_HIRA = {c: c - 0x60 for c in range(0x30A1, 0x30F7)}

# Inflecting words absorb the auxiliaries that follow them, so 食べられなかった
# is one clickable unit that looks up 食べる.
_INFLECTING = {"動詞", "形容詞"}
_NOT_WORDS = {"補助記号", "空白"}
# The tokenizer's dictionary prefers formal readings; these are the everyday ones.
_READINGS = {"私": "ワタシ", "言う": "イウ"}


def kata_to_hira(text):
    return text.translate(_KATA_TO_HIRA)


def _romaji_table():
    rows = {
        "": "あいうえお", "k": "かきくけこ", "s": "さしすせそ", "t": "たちつてと",
        "n": "なにぬねの", "h": "はひふへほ", "m": "まみむめも", "r": "らりるれろ",
        "g": "がぎぐげご", "z": "ざじずぜぞ", "d": "だぢづでど", "b": "ばびぶべぼ",
        "p": "ぱぴぷぺぽ",
    }
    table = {kana: stem + vowel for stem, row in rows.items() for kana, vowel in zip(row, "aiueo")}
    table.update({
        "し": "shi", "ち": "chi", "つ": "tsu", "ふ": "fu", "じ": "ji", "ぢ": "ji", "づ": "zu",
        "や": "ya", "ゆ": "yu", "よ": "yo", "わ": "wa", "ゐ": "i", "ゑ": "e", "を": "o", "ゔ": "vu",
        "ぁ": "a", "ぃ": "i", "ぅ": "u", "ぇ": "e", "ぉ": "o", "ゃ": "ya", "ゅ": "yu", "ょ": "yo",
    })
    # きゃ -> kya, しゃ -> sha, じゃ -> ja ...
    for kana in "きしちにひみりぎじぢびぴ":
        stem = table[kana][:-1]
        for small, vowel in zip("ゃゅょ", "auo"):
            table[kana + small] = stem + ("" if stem in ("sh", "ch", "j") else "y") + vowel
    # Sounds that only occur in loanwords.
    table.update({
        "ふぁ": "fa", "ふぃ": "fi", "ふぇ": "fe", "ふぉ": "fo", "ふゅ": "fyu",
        "うぃ": "wi", "うぇ": "we", "うぉ": "wo",
        "ゔぁ": "va", "ゔぃ": "vi", "ゔぇ": "ve", "ゔぉ": "vo",
        "てぃ": "ti", "でぃ": "di", "とぅ": "tu", "どぅ": "du", "てゅ": "tyu", "でゅ": "dyu",
        "しぇ": "she", "じぇ": "je", "ちぇ": "che",
        "つぁ": "tsa", "つぃ": "tsi", "つぇ": "tse", "つぉ": "tso",
    })
    return table


_ROMAJI = _romaji_table()
_MACRONS = {"a": "ā", "i": "ī", "u": "ū", "e": "ē", "o": "ō"}
# Particles written with one kana but pronounced as another.
_PARTICLE_ROMAJI = {"は": "wa", "へ": "e", "を": "o"}


# Vowel pairs written as one long vowel (ei and ii stay as they are).
_LONG_VOWELS = {("a", "a"), ("u", "u"), ("e", "e"), ("o", "o"), ("o", "u")}
# Words where two vowels meet across a kanji boundary and are not a long vowel
# (ba-ai, mizu-umi, ino-ue). The readings give no way to detect these.
_NO_LONG_VOWELS = {"場合", "湖", "井上", "子牛", "仔牛", "小売", "小売り"}


def romanize(segments):
    """Hepburn romaji with macrons for long vowels (とうきょう -> tōkyō).

    `segments` is a list of (kana, joins_previous, joins_inside). A vowel only
    lengthens the one before it where joining is allowed, which keeps word
    endings apart from stems (思う -> omou, not omō).
    Returns "" if the text contains anything that is not kana.
    """
    syllables = []  # [romaji, may lengthen the previous syllable]
    double = False
    for kana, joins_previous, joins_inside in segments:
        kana = kata_to_hira(kana)
        i = 0
        while i < len(kana):
            char = kana[i]
            pair = kana[i : i + 2]
            joins = joins_inside if i else joins_previous
            if char == "っ":
                double = True
                i += 1
                continue
            if char == "ー":
                if syllables and syllables[-1][0][-1:] in _MACRONS:
                    last = syllables[-1][0]
                    syllables[-1][0] = last[:-1] + _MACRONS[last[-1]]
                i += 1
                continue
            if char == "ん":
                following = kana[i + 1 : i + 2]
                apostrophe = following and following in "あいうえおやゆよ"
                syllables.append(["n'" if apostrophe else "n", False])
                i += 1
                continue
            if pair in _ROMAJI:
                syllable, i = _ROMAJI[pair], i + 2
            elif char in _ROMAJI:
                syllable, i = _ROMAJI[char], i + 1
            else:
                return ""
            if double and syllable[0] not in "aiueo":
                syllable = ("t" if syllable.startswith("ch") else syllable[0]) + syllable
            double = False
            syllables.append([syllable, joins])

    out = []
    for syllable, joins in syllables:
        if joins and out and (out[-1][-1:], syllable) in _LONG_VOWELS:
            out[-1] = out[-1][:-1] + _MACRONS[out[-1][-1]]
        else:
            out.append(syllable)
    return "".join(out)


def to_romaji(kana):
    return romanize([(kana, False, True)])


def _segments(surface, reading, pos):
    """Romanization segments for one token; see romanize()."""
    if not _HAS_JAPANESE.search(surface):
        # Digits and Latin text get unreliable readings (15 -> イチゴ).
        return []
    if pos[0] == "助動詞" and surface == "う":
        # Volitional ending: 行こ + う -> ikō.
        return [(reading, True, True)]
    if surface in _NO_LONG_VOWELS:
        return [(reading, False, False)]
    plain_form = pos[5].startswith(("終止形", "連体形"))
    if pos[0] == "動詞" and plain_form and surface.endswith("う") and len(reading) > 1:
        # The final う is the verb ending, not part of a long vowel (unlike
        # the volitional 行こう -> ikō).
        return [(reading[:-1], False, True), (reading[-1], False, True)]
    return [(reading, False, True)]


def has_kanji(text):
    return bool(_HAS_KANJI.search(text))


def furigana(surface, reading):
    """Return [[text, reading-or-None], ...] with readings only over kanji."""
    if not has_kanji(surface) or not reading:
        return [[surface, None]]
    reading = kata_to_hira(reading)
    runs = _RUNS.findall(surface)
    pattern = "".join(
        "(.+?)" if has_kanji(run) else re.escape(kata_to_hira(run)) for run in runs
    )
    match = re.fullmatch(pattern, reading)
    if not match:
        return [[surface, reading]]
    groups = iter(match.groups())
    return [[run, next(groups) if has_kanji(run) else None] for run in runs]


class Analyzer:
    def __init__(self):
        self._tokenizer = dictionary.Dictionary().tokenizer(
            mode=tokenizer.Tokenizer.SplitMode.C
        )

    def analyze(self, text):
        words = []
        for m in self._tokenizer.tokenize(text):
            surface = m.surface()
            pos = m.part_of_speech()
            if pos[0] in _NOT_WORDS or not surface.strip():
                words.append({"s": surface, "x": 1})
                continue
            reading = _READINGS.get(surface, m.reading_form())
            part = {"s": surface, "l": m.dictionary_form(), "p": pos[0]}
            kana = _segments(surface, reading, pos)
            prev = words[-1] if words else None
            attaches = pos[0] == "助動詞" or (
                pos[0] == "助詞" and pos[1] == "接続助詞" and surface in ("て", "で")
            )
            if attaches and prev and prev.get("p") in _INFLECTING:
                prev["s"] += surface
                prev["f"] += furigana(surface, reading)
                prev["k"] += kana
                prev["parts"].append(part)
                continue
            words.append({
                **part,
                "n": m.normalized_form(),
                "r": kata_to_hira(reading),
                "f": furigana(surface, reading),
                "k": kana,
                "parts": [part],
            })
        for word in words:
            if "x" in word:
                continue
            # Romanize the whole unit at once so a small っ carries across
            # the join (行っ + て -> itte).
            segments = word.pop("k")
            if word["p"] == "助詞" and word["s"] in _PARTICLE_ROMAJI:
                word["ro"] = _PARTICLE_ROMAJI[word["s"]]
            else:
                word["ro"] = romanize(segments)
            # Single-part words carry no extra breakdown.
            if len(word["parts"]) == 1:
                del word["parts"]
        return words
