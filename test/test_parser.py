"""Tests for the ANTLR parser layer."""
import unittest

from fileseq._vendor.antlr4 import InputStream, CommonTokenStream  # type: ignore[attr-defined]
from fileseq._vendor.antlr4.atn.PredictionMode import PredictionMode  # type: ignore[attr-defined]

from fileseq.parser.fileseqLexer import fileseqLexer
from fileseq.parser.fileseqParser import fileseqParser
from fileseq.parser.parse import FileSeqErrorListener, parse_file_sequence

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

# Inputs containing characters the lexer cannot tokenize. These must be
# rejected, not accepted with the bad characters silently dropped.
LEXER_ERROR_INPUTS = [
    "/a/foo<bar.exr",
    "/a/foo>bar.1-10#.exr",
    "/a/sh<010.1001.exr",
    "/a/x<y>.#.exr",
]

# Padding-like characters in directory segments are valid POSIX paths.
# Padding only has meaning in the final path component.
DIR_PADDING_INPUTS = [
    ("/mnt/shot#1/file.1-10#.exr", "/mnt/shot#1/", "file."),
    ("/mnt/a@b/file.1001.exr", "/mnt/a@b/", "file."),
    ("/mnt/a@b/file.exr", "/mnt/a@b/", "file"),
    ("/mnt/$FOO/file.1-10#.exr", "/mnt/$FOO/", "file."),
    ("/mnt/out/100%done/file.1-10#.exr", "/mnt/out/100%done/", "file."),
    ("/mnt/out/%04dir/file.exr", "/mnt/out/%04dir/", "file"),
    ("/mnt/<UDIM>/tex.1001.exr", "/mnt/<UDIM>/", "tex."),
    ("/mnt/%(UDIM)d/tex.#.exr", "/mnt/%(UDIM)d/", "tex."),
]

# A dot-number after a frame range without a step is the frame number, with
# the range text kept in the basename, as in v2. Only a decimal step value
# (1-5x0.25) may carry a decimal suffix.
RANGE_DOT_NUM_INPUTS = [
    ("/mnt/out/file.1-100.5#.exr", "file.1-100.", "5", "#"),
    ("/mnt/out/file.1-100.5@.exr", "file.1-100.", "5", "@"),
    ("/mnt/out/file.1,2,3.10#.exr", "file.1,2,3.", "10", "#"),
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

    def test_directory_padding_chars_parse_with_sll(self):
        for path, _, _ in DIR_PADDING_INPUTS:
            with self.subTest(path=path):
                self.assertEqual(_sll_errors(path), [])


class TestDirectoryPaddingChars(unittest.TestCase):

    def test_directory_allows_padding_chars(self):
        for path, dirname, basename in DIR_PADDING_INPUTS:
            with self.subTest(path=path):
                result = parse_file_sequence(path)
                self.assertEqual(result.directory, dirname)
                self.assertEqual(result.basename, basename)


class TestRangeFollowedByDotNum(unittest.TestCase):

    def test_range_followed_by_dot_num(self):
        for path, basename, frame, pad in RANGE_DOT_NUM_INPUTS:
            with self.subTest(path=path):
                result = parse_file_sequence(path)
                self.assertEqual(
                    (result.basename, result.frame_range, result.padding, result.extension),
                    (basename, frame, pad, ".exr"))

    def test_decimal_step_keeps_suffix(self):
        result = parse_file_sequence("/mnt/out/file.1-5x0.25#.exr")
        self.assertEqual((result.basename, result.frame_range), ("file.", "1-5x0.25"))


class TestLexerErrors(unittest.TestCase):

    def test_lexer_errors_are_rejected(self):
        for path in LEXER_ERROR_INPUTS:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    parse_file_sequence(path)


if __name__ == '__main__':
    unittest.main(verbosity=1)
