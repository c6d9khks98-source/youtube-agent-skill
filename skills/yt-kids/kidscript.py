#!/usr/bin/env python3
"""Lint a kids cartoon episode script for young ears.

Usage:
    python3 kidscript.py episode.txt --age 2-4
    python3 kidscript.py episode.txt --age 4-6 --wpm 120 --json

Script format: one line per spoken line. "NAME: words" is dialogue,
lines in [brackets] or (parentheses) are shots, actions or SFX and are
not counted as speech. "SHOT 3:" / "SCENE:" headers are skipped too.

It checks what a preschool script gets wrong most often: lines too long
to follow, words too long to say, no refrain, not enough questions to the
viewer, and a runtime that does not fit the slot. It is a heuristic. A
clean report means nothing is obviously wrong, not that it is good.
"""
import argparse
import json
import re
import sys
from collections import Counter

# Per age band: max words per spoken line, max syllables per word,
# seconds between viewer questions, target runtime range in seconds.
BANDS = {
    "0-2": {"line": 6, "syl": 2, "ask": 45, "runtime": (60, 180)},
    "2-4": {"line": 10, "syl": 3, "ask": 40, "runtime": (90, 240)},
    "4-6": {"line": 14, "syl": 3, "ask": 40, "runtime": (120, 300)},
    "6-8": {"line": 18, "syl": 4, "ask": 60, "runtime": (180, 480)},
}

SKIP = re.compile(r"^\s*(\[.*\]|\(.*\)|(SHOT|SCENE|INT\.|EXT\.)\b.*)\s*$", re.I)
SPEAKER = re.compile(r"^\s*([A-Z][A-Za-z0-9 _'-]{0,30}):\s*(.*)$")
INLINE_DIRECTION = re.compile(r"\[[^\]]*\]|\([^)]*\)")
WORD = re.compile(r"[A-Za-z']+")


def syllables(word):
    w = word.lower().strip("'")
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def normalise(line):
    return " ".join(WORD.findall(line.lower()))


def parse(text):
    spoken = []
    for n, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or SKIP.match(raw):
            continue
        m = SPEAKER.match(raw)
        speaker, words = (m.group(1).strip(), m.group(2)) if m else ("", raw)
        words = INLINE_DIRECTION.sub("", words).strip()
        if WORD.search(words):
            spoken.append({"n": n, "speaker": speaker, "text": words})
    return spoken


def lint(text, age, wpm):
    band = BANDS[age]
    lines = parse(text)
    if not lines:
        return {"error": "no spoken lines found"}

    total_words = sum(len(WORD.findall(l["text"])) for l in lines)
    runtime = round(total_words / wpm * 60)

    long_lines = [
        {"line": l["n"], "words": len(WORD.findall(l["text"])), "text": l["text"]}
        for l in lines
        if len(WORD.findall(l["text"])) > band["line"]
    ]
    hard_words = sorted({
        w for l in lines for w in WORD.findall(l["text"]) if syllables(w) > band["syl"]
    })

    counts = Counter(normalise(l["text"]) for l in lines)
    refrain, refrain_n = counts.most_common(1)[0]
    questions = sum(l["text"].count("?") for l in lines)
    wanted_questions = max(1, runtime // band["ask"])

    issues = []
    if long_lines:
        issues.append(f"{len(long_lines)} line(s) over {band['line']} words for age {age}")
    if hard_words:
        issues.append(f"{len(hard_words)} word(s) over {band['syl']} syllables (estimated)")
    if refrain_n < 3:
        issues.append("no line repeats 3+ times - give it a refrain")
    if questions < wanted_questions:
        issues.append(f"{questions} question(s) to the viewer, want at least {wanted_questions}")
    lo, hi = band["runtime"]
    if not lo <= runtime <= hi:
        issues.append(f"runtime ~{runtime}s at {wpm} wpm, outside {lo}-{hi}s for age {age}")

    return {
        "age": age,
        "spoken_lines": len(lines),
        "words": total_words,
        "runtime_seconds": runtime,
        "wpm_assumed": wpm,
        "refrain": {"text": refrain, "times": refrain_n},
        "questions": questions,
        "long_lines": long_lines,
        "hard_words": hard_words,
        "issues": issues,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("script", help="episode script, plain text ('-' for stdin)")
    ap.add_argument("--age", choices=sorted(BANDS), default="2-4")
    ap.add_argument("--wpm", type=int, default=110,
                    help="speaking pace; kids voice-over runs slower than adult (default 110)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    text = sys.stdin.read() if a.script == "-" else open(a.script, encoding="utf-8").read()
    r = lint(text, a.age, a.wpm)
    if "error" in r:
        print(r["error"], file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(r, indent=2))
        return 1 if r["issues"] else 0

    print(f"age {r['age']} | {r['spoken_lines']} spoken lines | {r['words']} words | "
          f"~{r['runtime_seconds']}s at {r['wpm_assumed']} wpm")
    print(f"refrain: \"{r['refrain']['text']}\" x{r['refrain']['times']} | "
          f"questions to viewer: {r['questions']}")
    for l in r["long_lines"]:
        print(f"  long  line {l['line']} ({l['words']} words): {l['text']}")
    if r["hard_words"]:
        print("  hard  " + ", ".join(r["hard_words"]))
    print()
    if r["issues"]:
        for i in r["issues"]:
            print(f"FIX  {i}")
        return 1
    print("clean - nothing obviously wrong. Read it out loud anyway.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
