"""Tests for the ANTLR parser layer."""
import unittest

from fileseq._vendor.antlr4 import InputStream, CommonTokenStream  # type: ignore[attr-defined]
from fileseq._vendor.antlr4.atn.PredictionMode import PredictionMode  # type: ignore[attr-defined]

from fileseq.parser.fileseqLexer import fileseqLexer
from fileseq.parser.fileseqParser import fileseqParser
from fileseq.parser.parse import FileSeqErrorListener

# Valid inputs that must parse with SLL prediction alone. A grammar change that
# makes any of these fall back to full LL prediction is a large performance
# regression (roughly 10x for range sequences).
SLL_INPUTS = [
    "/mnt/projects/show/shots/sh010/comp/v012/sh010_comp_v012.1001-1240#.exr",
    "/mnt/projects/show/shots/sh010/plates/sh010_plate.1001.dpx",
    "/renders/beauty/beauty.1-100x2,150-200@@@@.tif",
    "/mnt/projects/show/assets/chars/hero/model/hero_model_v003.abc",
    "/path/file.1-100#.exr",
    "/path/file1-100#.exr",
    "/path/file.100.exr",
    "/path/file.txt",
    "/path/to/file:1-1x1#.exr",
    "/path/file.-10-100#.exr",
    "/path/file.1-100x0.25#.exr",
    "/path/file.1,2,3,5-10@@.exr",
    "/path/file.#.exr",
    "/path/file.@@@@.exr",
    "/path/file.%04d.exr",
    "/path/file.$F4.exr",
    "/path/tex.<UDIM>.exr",
    "/path/tex.%(UDIM)d.exr",
    "/path/.hidden5.1-10#.7zip",
    "/path/.hidden.100.ext",
    "/path/1-100#.exr",
    "/path/@@@.exr",
    "/path/name_2025-05-13_v1.1-10#.exr",
    "/path/file.1-10#_exr",
    "/path/file.1-10#.tar.gz",
    "//server/share/file.1-10#.exr",
    "C:\\path\\file.1-10#.exr",
    "relative/file.1001-1100#.exr",
    "file.1-10#.exr",
]


def _sll_errors(path):
    lexer = fileseqLexer(InputStream(path))
    parser = fileseqParser(CommonTokenStream(lexer))
    errors = FileSeqErrorListener()
    lexer.removeErrorListeners()
    lexer.addErrorListener(errors)
    parser.removeErrorListeners()
    parser.addErrorListener(errors)
    parser._interp.predictionMode = PredictionMode.SLL
    parser.input_()
    return errors.errors


class TestSLLPrediction(unittest.TestCase):

    def test_valid_inputs_parse_with_sll(self):
        for path in SLL_INPUTS:
            with self.subTest(path=path):
                self.assertEqual(_sll_errors(path), [])


if __name__ == '__main__':
    unittest.main(verbosity=1)
