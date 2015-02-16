#! /usr/bin/env python
"""
filesequence - A parsing object representing sequential files for fileseq.
"""

import os
from glob import iglob
from itertools import imap, ifilter
from fileseq.exceptions import ParseException, FileSeqException
from fileseq.constants import PAD_MAP, DISK_RE, SPLIT_RE
from fileseq.frameset import FrameSet

class FileSequence(object):
    """
    FileSequence represents an ordered sequence of files.
    """
    def __init__(self, sequence):
        """
        Initialize the FileSequence.
        :param sequence: string (ie: dir/path.1-100#.ext)
        :return: None
        """
        if not hasattr(self, '_frameSet'):

            self._frameSet = None

            try:
                # the main case, we've got path.1-100#.exr
                path, frames, self._pad, self._ext = SPLIT_RE.split(sequence, 1)
                self._dir, self._base = os.path.split(path)
                self._frameSet = FrameSet(frames)
            except ValueError:
                # edge case 1; we've got an invalid pad
                for placeholder in PAD_MAP.keys():
                    if placeholder in sequence:
                        msg = "Failed to parse FileSequence: {0}"
                        raise ParseException(msg.format(sequence))
                # edge case 2; we've got a single frame of a sequence
                a_frame = DISK_RE.match(sequence)
                if a_frame:
                    self._dir, self._base, frames, self._ext = a_frame.groups()
                    self._frameSet = FrameSet(frames)
                    self._pad = FileSequence.getPaddingChars(len(frames))
                # edge case 3; we've got a solitary file, not a sequence
                else:
                    path, self._ext = os.path.splitext(sequence)
                    self._dir, self._base = os.path.split(path)
                    self._pad = ''

        if self._dir:
            if not self._dir.endswith(os.sep):
                self._dir += os.sep
        else:
            self._dir = ''

        self._zfill = sum([PAD_MAP[c] for c in self._pad])

    def format(self, template="{basename}{range}{padding}{extension}"):
        """
        Return the file sequence as a formatted string according to
        the given template.

        Utilizes the python string format syntax.  Available keys include:
            * basename - the basename of the sequence.
            * extension - the file extension of the sequence.
            * start - the start frame.
            * end - the end frame.
            * length - the length of the frame range.
            * padding - the detecting amount of padding.
            * inverted - the inverted frame range. (returns "" if none)
            * dirname - the directory name.

        :param template: str
        :return: str
        """
        return template.format(
            basename=self.basename(),
            extension=self.extension(), start=self.start(),
            end=self.end(), length=len(self),
            padding=self.padding(),
            range=self.frameRange() or "",
            inverted=self.invertedFrameRange() or "",
            dirname=self.dirname())

    def split(self):
        """
        Split the FileSequence into contiguous pieces and return them as a list
        of FileSequence instances.
        :return: list
        """
        result = []
        for frange in self.frameRange().split(","):
            result.append(FileSequence(''.join(
                (self._dir, self._base, frange, self._pad, self._ext))))
        return result

    def dirname(self):
        """
        Return the directory name of the sequence.
        :return: str
        """
        return self._dir

    def setDirname(self, dirname):
        """
        Set a new directory name for the sequence.
        :param dirname: the new directory name (str)
        :return: None
        """
        self._dir = dirname

    def basename(self):
        """
        Return the basename of the sequence.
        :return: str
        """
        return self._base

    def setBasename(self, base):
        """
        Set a new basename for the sequence.
        :param base: the new base name (str)
        :return: None
        """
        self._base = base

    def padding(self):
        """
        Return the the padding characters in the sequence.
        :return: str
        """
        return self._pad

    def setPadding(self, padding):
        """
        Set new padding characters for the sequence.
        i.e. "#" or "@@@", or an empty string to disable range formatting.
        :param padding: str
        :return: None
        """
        self._pad = padding
        self._zfill = sum([PAD_MAP[c] for c in self._pad])

    def frameSet(self):
        """
        Return the FrameSet of the sequence if specified, otherwise None.
        :return: FrameSet or None
        """
        return self._frameSet

    def setFrameSet(self, frameSet):
        """
        Set a new FrameSet for the sequence.
        :param frameSet: the new FrameSet object
        :return: None
        """
        self._frameSet = frameSet

    def extension(self):
        """
        Return the file extension of the sequence, including leading period.
        :return: str
        """
        return self._ext

    def setExtension(self, ext):
        """
        Set a new file extension for the sequence.
        :param ext: the new file extension (a leading period will be added if
        none is provided).
        :return: None
        """
        if ext[0] != ".":
            ext = "." + ext
        self._ext = ext

    def setExtention(self, ext):
        """
        Deprecated: use setExtension.
        """
        import warnings
        msg = "the setExtention method is deprecated, please use setExtension"
        warnings.warn(msg)
        self.setExtension(ext)

    def frameRange(self):
        """
        Returns the string formatted frame range of the sequence.
        Will return an empty string if the sequence has no frame pattern.
        :return: str
        """
        if not self._frameSet:
            return ''
        return self._frameSet.frameRange(self._zfill)

    def setFrameRange(self, frange):
        """
        Set a new frame range for the sequence.
        :param frange: a properly formatted frame range, as per FrameSet
        :return: None
        """
        self._frameSet = FrameSet(frange)

    def invertedFrameRange(self):
        """
        Returns the inverse string formatted frame range of the sequence.
        Will return an empty string if the sequence has no frame pattern.
        :return: str
        """
        if not self._frameSet:
            return ''
        return self._frameSet.invertedFrameRange(self._zfill)

    def start(self):
        """
        Returns the start frame of the sequences FrameSet.
        Will return 0 if the sequence has no frame pattern.
        :return: int
        """
        if not self._frameSet:
            return 0
        return self._frameSet.start()

    def end(self):
        """
        Returns the end frame of the sequences FrameSet.
        Will return 0 if the sequence has no frame pattern.
        :return: int
        """
        if not self._frameSet:
            return 0
        return self._frameSet.end()

    def zfill(self):
        """
        Returns the zfill depth (ie the number of zeroes to pad with).
        :return: int
        """
        return self._zfill

    def frame(self, frame):
        """
        Return a path go the given frame in the sequence.  Integer or string
        digits are treated as a frame number and padding is applied, all other
        values are passed though.

        Example:
            seq.frame(1)
            >> /foo/bar.0001.exr
            seq.frame("#")
            >> /foo/bar.#.exr

        :param frame: the desired frame number (int/str) or a char to pass
        through (ie. #)
        :return: str
        """
        try:
            zframe = str(int(frame)).zfill(self._zfill)
        except ValueError:
            zframe = frame

        # There may have been no placeholder for frame IDs in
        # the sequence, in which case we don't want to insert
        # a frame ID

        if self._zfill == 0:
            zframe = ""

        return "".join((self._dir, self._base, zframe, self._ext))

    def index(self, idx):
        """
        Return the path to the file at the given index.
        :param idx: the desired index (int)
        :return: str
        """
        if not self._frameSet:
            return str(self)
        return self.frame(self._frameSet[idx])

    def __iter__(self):
        """
        Allow iteration over the path or paths this FileSequence represents.
        :return: generator
        """
        # If there is no frame range, or there is no padding
        # characters, then we only want to represent a single path
        if not self._frameSet or not self._zfill:
            yield str(self)
            return

        for f in self._frameSet:
            yield self.frame(f)

    def __getitem__(self, idx):
        """
        Allows access via index to the underlying FrameSet.
        :param idx: the desired index (int)
        :return: int
        """
        return self.index(idx)

    def __len__(self):
        """
        The length (number of files) represented by this FileSequence.
        :return: int
        """
        if not self._frameSet or not self._zfill:
            return 1
        return len(self._frameSet)

    def __str__(self):
        """
        String representation of this FileSequence.
        :return: str
        """
        return "".join((
            self._dir,
            self._base,
            str(self._frameSet or ""),
            self._pad,
            self._ext))

    @staticmethod
    def yield_sequences_in_list(paths):
        """
        Yield the discreet sequences within paths.  This does not try to
        determine if the files actually exist on disk, it assumes you already
        know that.
        :param paths: a list of paths
        :return: generator
        """
        seqs = {}
        _check = DISK_RE.match
        for match in ifilter(None, imap(_check, paths)):
            dirname, basename, frame, ext = match.groups()
            key = (dirname, basename, ext)
            seqs.setdefault(key, set())
            seqs[key].add(frame)
        for (dirname, basename, ext), frames in seqs.iteritems():
            # build the FileSequence behind the scenes, rather than dupe work
            seq = FileSequence.__new__(FileSequence)
            seq._dir = dirname
            seq._base = basename
            seq._frameSet = FrameSet(set(imap(int, frames)))
            seq._pad = FileSequence.getPaddingChars(min(imap(len, frames)))
            seq._ext = ext
            seq.__init__(str(seq))
            yield seq

    @staticmethod
    def findSequencesInList(paths):
        """
        Returns the list of discreet sequences within paths.  This does not try
        to determine if the files actually exist on disk, it assumes you
        already know that.
        :param paths: a list of paths
        :return: list
        """
        return list(FileSequence.yield_sequences_in_list(paths))

    @staticmethod
    def findSequencesOnDisk(dirpath):
        """
        Yield the sequences found in the given directory.
        :param dirpath: directory to scan
        :return: list
        """
        # reserve some functions we're going to need quick access to
        _isfile = os.path.isfile
        _join = os.path.join
        # collapse some generators to get us the files that match our regex
        files = (_join(dirpath, f) for f in os.listdir(dirpath))
        files = ifilter(_isfile, files)
        return list(FileSequence.yield_sequences_in_list(files))

    @staticmethod
    def findSequenceOnDisk(pattern):
        """
        Search for a specific sequence on disk.
        For Example:
            findSequenceOnDisk("seq/bar#.exr") # or any fileseq pattern
        :param pattern: the sequence pattern being searched for
        :return: str
        :raises: FileSeqException if no sequence is found on disk
        """
        seq = FileSequence(pattern)
        patt = seq.format('{dirname}{basename}*{extension}')
        try:
            return FileSequence.yield_sequences_in_list(iglob(patt)).next()
        except StopIteration:
            msg = 'no sequence found on disk matching {0}'
            raise FileSeqException(msg.format(pattern))

    @staticmethod
    def getPaddingChars(num):
        """
        Given a particular amount of padding, return the proper padding characters.
        """
        if num == 0:
            return "@"
        if num % 4 == 0:
            return "#" * (num / 4)
        else:
            return "@" * num
