# Generated from fileseq.g4 by ANTLR 4.13.1
from antlr4 import *
if "." in __name__:
    from .fileseqParser import fileseqParser
else:
    from fileseqParser import fileseqParser

# This class defines a complete generic visitor for a parse tree produced by fileseqParser.

class fileseqVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by fileseqParser#input.
    def visitInput(self, ctx:fileseqParser.InputContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#sequence.
    def visitSequence(self, ctx:fileseqParser.SequenceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#patternOnly.
    def visitPatternOnly(self, ctx:fileseqParser.PatternOnlyContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#singleFrame.
    def visitSingleFrame(self, ctx:fileseqParser.SingleFrameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#plainFile.
    def visitPlainFile(self, ctx:fileseqParser.PlainFileContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#directory.
    def visitDirectory(self, ctx:fileseqParser.DirectoryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#basenameChar.
    def visitBasenameChar(self, ctx:fileseqParser.BasenameCharContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#plainBasenameChar.
    def visitPlainBasenameChar(self, ctx:fileseqParser.PlainBasenameCharContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#dirSegment.
    def visitDirSegment(self, ctx:fileseqParser.DirSegmentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#basename.
    def visitBasename(self, ctx:fileseqParser.BasenameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#plainBasename.
    def visitPlainBasename(self, ctx:fileseqParser.PlainBasenameContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#frameRange.
    def visitFrameRange(self, ctx:fileseqParser.FrameRangeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#frameNum.
    def visitFrameNum(self, ctx:fileseqParser.FrameNumContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#padding.
    def visitPadding(self, ctx:fileseqParser.PaddingContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by fileseqParser#extension.
    def visitExtension(self, ctx:fileseqParser.ExtensionContext):
        return self.visitChildren(ctx)



del fileseqParser