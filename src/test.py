import fileseq

seqs = fileseq.findSequencesOnDisk("/Users/gregcotten/Temp/filesequence")
for seq in seqs:
	print seq.format("{dirname}{basename}[{range}]{extension} | Missing: {missing}", uniquePerFrameRange = False)