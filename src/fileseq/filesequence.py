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
    """:class:`FileSequence` represents an ordered sequence of files.

    :type sequence: str
    :param sequence: (ie: dir/path.1-100#.ext)
    """
    def __init__(self, sequence):
        if not hasattr(self, '_frameSet'):

            self._frameSet = None

            try:
                # the main case, padding characters in the path.1-100#.exr
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
                    # edge case 3: we've got a single versioned file, not a sequence
                    if frames and not self._base.endswith('.'):
                        self._base = self._base + frames
                        self._pad = ''
                    elif not frames:
                        self._pad = ''
                        self._frameSet = None
                    else:
                        self._frameSet = FrameSet(frames)
                        if self._frameSet:
                            self._pad = FileSequence.getPaddingChars(len(frames))
                        else:
                            self._pad = ''
                            self._frameSet = None
                # edge case 4; we've got a solitary file, not a sequence
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
        """Return the file sequence as a formatted string according to
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

        :type template: str
        :rtype: str
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
        Split the :class:`FileSequence` into contiguous pieces and return them
        as a list of :class:`FileSequence` instances.

        :rtype: list
        """
        result = []
        for frange in self.frameRange().split(","):
            result.append(FileSequence(''.join(
                (self._dir, self._base, frange, self._pad, self._ext))))
        return result

    def dirname(self):
        """
        Return the directory name of the sequence.

        :rtype: str
        """
        return self._dir

    def setDirname(self, dirname):
        """
        Set a new directory name for the sequence.

        :type dirname: str
        :param dirname: the new directory name
        :rtype: None
        """
        self._dir = dirname

    def basename(self):
        """
        Return the basename of the sequence.

        :rtype: str
        """
        return self._base

    def setBasename(self, base):
        """
        Set a new basename for the sequence.

        :type base: str
        :param base: the new base name
        :rtype: None
        """
        self._base = base

    def padding(self):
        """
        Return the the padding characters in the sequence.

        :rtype: str
        """
        return self._pad

    def setPadding(self, padding):
        """
        Set new padding characters for the sequence.
        i.e. "#" or "@@@", or an empty string to disable range formatting.

        :type padding: str
        :rtype: None
        """
        self._pad = padding
        self._zfill = sum([PAD_MAP[c] for c in self._pad])

    def frameSet(self):
        """
        Return the :class:`fileseq.frameset.FrameSet` of the sequence if specified,
        otherwise None.

        :rtype: :class:`fileseq.frameset.FrameSet` or None
        """
        return self._frameSet

    def setFrameSet(self, frameSet):
        """
        Set a new :class:`fileseq.frameset.FrameSet` for the sequence.

        :param frameSet: the new :class:`fileseq.frameset.FrameSet` object
        :rtype: None
        """
        self._frameSet = frameSet

    def extension(self):
        """
        Return the file extension of the sequence, including leading period.

        :rtype: str
        """
        return self._ext

    def setExtension(self, ext):
        """
        Set a new file extension for the sequence.

        .. note::
            A leading period will be added if none is provided.

        :param ext: the new file extension
        :rtype: None
        """
        if ext[0] != ".":
            ext = "." + ext
        self._ext = ext

    def setExtention(self, ext):
        """
        Deprecated: use :meth:`setExtension`.
        """
        import warnings
        msg = "the setExtention method is deprecated, please use setExtension"
        warnings.warn(msg)
        self.setExtension(ext)

    def frameRange(self):
        """
        Returns the string formatted frame range of the sequence.
        Will return an empty string if the sequence has no frame pattern.

        :rtype: str
        """
        if not self._frameSet:
            return ''
        return self._frameSet.frameRange(self._zfill)

    def setFrameRange(self, frange):
        """
        Set a new frame range for the sequence.

        :param frange: a properly formatted frame range, as per :class:`fileseq.frameset.FrameSet`
        :rtype: None
        """
        self._frameSet = FrameSet(frange)

    def invertedFrameRange(self):
        """
        Returns the inverse string formatted frame range of the sequence.
        Will return an empty string if the sequence has no frame pattern.

        :rtype: str
        """
        if not self._frameSet:
            return ''
        return self._frameSet.invertedFrameRange(self._zfill)

    def start(self):
        """
        Returns the start frame of the sequence's :class:`fileseq.frameset.FrameSet`.
        Will return 0 if the sequence has no frame pattern.

        :rtype: int
        """
        if not self._frameSet:
            return 0
        return self._frameSet.start()

    def end(self):
        """
        Returns the end frame of the sequences :class:`fileseq.frameset.FrameSet`.
        Will return 0 if the sequence has no frame pattern.

        :rtype: int
        """
        if not self._frameSet:
            return 0
        return self._frameSet.end()

    def zfill(self):
        """
        Returns the zfill depth (ie the number of zeroes to pad with).

        :rtype: int
        """
        return self._zfill

    def frame(self, frame):
        """
        Return a path go the given frame in the sequence.  Integer or string
        digits are treated as a frame number and padding is applied, all other
        values are passed though.

        :Example:
                >>> seq.frame(1)
                /foo/bar.0001.exr
                >>> seq.frame("#")
                /foo/bar.#.exr

        :param frame: the desired frame number (int/str) or a char to pass through (ie. #)
        :rtype: str
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

        :type idx: int
        :param idx: the desired index
        :rtype: str
        """
        if not self._frameSet:
            return str(self)
        return self.frame(self._frameSet[idx])

    def __iter__(self):
        """
        Allow iteration over the path or paths this :class:`FileSequence`
        represents.

        :rtype: generator
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
        Allows access via index to the underlying :class:`fileseq.frameset.FrameSet`.

        :type idx: int
        :param idx: the desired index
        :rtype: int
        """
        return self.index(idx)

    def __len__(self):
        """
        The length (number of files) represented by this :class:`FileSequence`.

        :rtype: int
        """
        if not self._frameSet or not self._zfill:
            return 1
        return len(self._frameSet)

    def __str__(self):
        """
        String representation of this :class:`FileSequence`.

        :rtype: str
        """
        frameSet = str(self._frameSet or "")
        return "".join((
            self._dir,
            self._base,
            frameSet,
            self._pad if frameSet else "",
            self._ext))

    @staticmethod
    def yield_sequences_in_list(paths):
        """
        Yield the discrete sequences within paths.  This does not try to
        determine if the files actually exist on disk, it assumes you already
        know that.

        :param paths: a list of paths
        :rtype: generator
        """
        seqs = {}
        _check = DISK_RE.match
        for match in ifilter(None, imap(_check, paths)):
            dirname, basename, frame, ext = match.groups()
            if not basename and not ext:
                continue
            key = (dirname, basename, ext)
            seqs.setdefault(key, set())
            if frame:
                seqs[key].add(frame)
        for (dirname, basename, ext), frames in seqs.iteritems():
            # build the FileSequence behind the scenes, rather than dupe work
            seq = FileSequence.__new__(FileSequence)
            seq._dir = dirname or ''
            seq._base = basename or ''
            seq._ext = ext or ''
            if frames:
                seq._frameSet = FrameSet(set(imap(int, frames))) if frames else None
                seq._pad = FileSequence.getPaddingChars(min(imap(len, frames)))
            else:
                seq._frameSet = None
                seq._pad = ''
            seq.__init__(str(seq))
            yield seq

    @staticmethod
    def findSequencesInList(paths):
        """
        Returns the list of discrete sequences within paths.  This does not try
        to determine if the files actually exist on disk, it assumes you
        already know that.

        :param paths: a list of paths
        :rtype: list
        """
        return list(FileSequence.yield_sequences_in_list(paths))

    @staticmethod
    def findSequencesOnDisk(dirpath, include_hidden=False):
        """
        Yield the sequences found in the given directory.

        :param dirpath: directory to scan
        :type include_hidden: bool
        :param include_hidden: if true, show .hidden files as well
        :rtype: list
        """
        # reserve some functions we're going to need quick access to
        _not_hidden = lambda f: not f.startswith('.')
        _isfile = os.path.isfile
        _join = os.path.join
        # collapse some generators to get us the files that match our regex
        files = os.listdir(dirpath)
        if not include_hidden:
            files = ifilter(_not_hidden, files)
        files = (_join(dirpath, f) for f in files)
        files = ifilter(_isfile, files)
        return list(FileSequence.yield_sequences_in_list(files))

    @staticmethod
    def findSequenceOnDisk(pattern):
        """
        Search for a specific sequence on disk.

        :Example:
            >>> findSequenceOnDisk("seq/bar#.exr") # or any fileseq pattern

        :param pattern: the sequence pattern being searched for
        :rtype: str
        :raises: :class:`fileseq.exceptions.FileSeqException` if no sequence is found on disk
        """
        seq = FileSequence(pattern)

        if seq.frameRange() == '' and seq.padding() == '':
            if os.path.isfile(pattern):
                return seq

        patt = seq.format('{dirname}{basename}*{extension}')

        ext = seq.extension()
        basename = seq.basename()

        matches = FileSequence.yield_sequences_in_list(iglob(patt))
        for match in matches:
            if match.basename() == basename and match.extension() == ext:
                return match

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
            return "#" * (num // 4)
        else:
            return "@" * num

    @staticmethod
    def getPaddingNum(chars):
        """
        Given a supported group of padding characters, return the amount of padding.

        :type chars: str
        :param chars: a supported group of padding characters
        :rtype: int
        :raises: ValueError if unsupported padding character is detected
        """
        try:
            return sum([PAD_MAP[char] for char in chars])
        except KeyError:
            msg = "Detected an unsupported padding character: \"{}\"."
            msg += " Supported padding characters: {}."
            raise ValueError(msg.format(char, str(PAD_MAP.keys())))
