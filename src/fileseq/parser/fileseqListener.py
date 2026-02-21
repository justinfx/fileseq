# Generated from fileseq.g4 by ANTLR 4.13.1
from antlr4 import *
if "." in __name__:
    from .fileseqParser import fileseqParser
else:
    from fileseqParser import fileseqParser

# This class defines a complete listener for a parse tree produced by fileseqParser.
class fileseqListener(ParseTreeListener):

    # Enter a parse tree produced by fileseqParser#input.
    def enterInput(self, ctx:fileseqParser.InputContext):
        pass

    # Exit a parse tree produced by fileseqParser#input.
    def exitInput(self, ctx:fileseqParser.InputContext):
        pass


    # Enter a parse tree produced by fileseqParser#sequence.
    def enterSequence(self, ctx:fileseqParser.SequenceContext):
        pass

    # Exit a parse tree produced by fileseqParser#sequence.
    def exitSequence(self, ctx:fileseqParser.SequenceContext):
        pass


    # Enter a parse tree produced by fileseqParser#patternOnly.
    def enterPatternOnly(self, ctx:fileseqParser.PatternOnlyContext):
        pass

    # Exit a parse tree produced by fileseqParser#patternOnly.
    def exitPatternOnly(self, ctx:fileseqParser.PatternOnlyContext):
        pass


    # Enter a parse tree produced by fileseqParser#singleFrame.
    def enterSingleFrame(self, ctx:fileseqParser.SingleFrameContext):
        pass

    # Exit a parse tree produced by fileseqParser#singleFrame.
    def exitSingleFrame(self, ctx:fileseqParser.SingleFrameContext):
        pass


    # Enter a parse tree produced by fileseqParser#plainFile.
    def enterPlainFile(self, ctx:fileseqParser.PlainFileContext):
        pass

    # Exit a parse tree produced by fileseqParser#plainFile.
    def exitPlainFile(self, ctx:fileseqParser.PlainFileContext):
        pass


    # Enter a parse tree produced by fileseqParser#directory.
    def enterDirectory(self, ctx:fileseqParser.DirectoryContext):
        pass

    # Exit a parse tree produced by fileseqParser#directory.
    def exitDirectory(self, ctx:fileseqParser.DirectoryContext):
        pass


    # Enter a parse tree produced by fileseqParser#dirSegment.
    def enterDirSegment(self, ctx:fileseqParser.DirSegmentContext):
        pass

    # Exit a parse tree produced by fileseqParser#dirSegment.
    def exitDirSegment(self, ctx:fileseqParser.DirSegmentContext):
        pass


    # Enter a parse tree produced by fileseqParser#sequenceBasename.
    def enterSequenceBasename(self, ctx:fileseqParser.SequenceBasenameContext):
        pass

    # Exit a parse tree produced by fileseqParser#sequenceBasename.
    def exitSequenceBasename(self, ctx:fileseqParser.SequenceBasenameContext):
        pass


    # Enter a parse tree produced by fileseqParser#patternBasename.
    def enterPatternBasename(self, ctx:fileseqParser.PatternBasenameContext):
        pass

    # Exit a parse tree produced by fileseqParser#patternBasename.
    def exitPatternBasename(self, ctx:fileseqParser.PatternBasenameContext):
        pass


    # Enter a parse tree produced by fileseqParser#singleFrameBasename.
    def enterSingleFrameBasename(self, ctx:fileseqParser.SingleFrameBasenameContext):
        pass

    # Exit a parse tree produced by fileseqParser#singleFrameBasename.
    def exitSingleFrameBasename(self, ctx:fileseqParser.SingleFrameBasenameContext):
        pass


    # Enter a parse tree produced by fileseqParser#plainBasename.
    def enterPlainBasename(self, ctx:fileseqParser.PlainBasenameContext):
        pass

    # Exit a parse tree produced by fileseqParser#plainBasename.
    def exitPlainBasename(self, ctx:fileseqParser.PlainBasenameContext):
        pass


    # Enter a parse tree produced by fileseqParser#frameRange.
    def enterFrameRange(self, ctx:fileseqParser.FrameRangeContext):
        pass

    # Exit a parse tree produced by fileseqParser#frameRange.
    def exitFrameRange(self, ctx:fileseqParser.FrameRangeContext):
        pass


    # Enter a parse tree produced by fileseqParser#frameNum.
    def enterFrameNum(self, ctx:fileseqParser.FrameNumContext):
        pass

    # Exit a parse tree produced by fileseqParser#frameNum.
    def exitFrameNum(self, ctx:fileseqParser.FrameNumContext):
        pass


    # Enter a parse tree produced by fileseqParser#padding.
    def enterPadding(self, ctx:fileseqParser.PaddingContext):
        pass

    # Exit a parse tree produced by fileseqParser#padding.
    def exitPadding(self, ctx:fileseqParser.PaddingContext):
        pass


    # Enter a parse tree produced by fileseqParser#extension.
    def enterExtension(self, ctx:fileseqParser.ExtensionContext):
        pass

    # Exit a parse tree produced by fileseqParser#extension.
    def exitExtension(self, ctx:fileseqParser.ExtensionContext):
        pass



del fileseqParser