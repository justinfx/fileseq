#!/usr/bin/env python
"""
Report the time to parse file sequence strings, so parser and grammar changes
can be compared against a baseline.

    python scripts/bench_parse.py
"""
import timeit
from pathlib import Path

import fileseq
from fileseq.parser.parse import parse_file_sequence

ROOT = Path(__file__).parent.parent
CORPUS_FILE = ROOT / "src" / "fileseq" / "grammar" / "parse_cases.tsv"
REPEATS = 5

INPUTS = {
    "sequence": "/mnt/projects/show/shots/sh010/comp/v012/sh010_comp_v012.1001-1240#.exr",
    "single": "/mnt/projects/show/shots/sh010/plates/sh010_plate.1001.dpx",
    "stepped": "/renders/beauty/beauty.1-100x2,150-200@@@@.tif",
    "plain": "/mnt/projects/show/assets/chars/hero/model/hero_model_v003.abc",
}


def best_micros(fn, number):
    return min(timeit.repeat(fn, number=number, repeat=REPEATS)) / number * 1e6


def load_corpus_inputs():
    inputs = []
    for line in CORPUS_FILE.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if cols[0] == "all" or "py" in cols[0].split(","):
            inputs.append(cols[2])
    return inputs


def parse_corpus(inputs):
    for path in inputs:
        try:
            parse_file_sequence(path)
        except ValueError:
            pass


def main():
    for name, path in INPUTS.items():
        us = best_micros(lambda: fileseq.FileSequence(path), 200)
        print(f"FileSequence/{name:9s} {us:10.1f} us/op")

    corpus = load_corpus_inputs()
    us = best_micros(lambda: parse_corpus(corpus), 2)
    print(f"ParseCorpus ({len(corpus)} inputs) {us:8.1f} us/op")


if __name__ == "__main__":
    main()
