#! /usr/bin/env python
"""
filesequence - A parsing object representing sequential files for fileseq.
"""

import os
import re
import functools
from glob import iglob
from itertools import imap, ifilter
from fileseq.exceptions import ParseException, FileSeqException
from fileseq.constants import PAD_MAP, DISK_RE, SPLIT_RE, PRINTF_SYNTAX_PADDING_RE
from fileseq.frameset import FrameSet
from fileseq import utils

class FileSequence(object):
    """:class:`FileSequence` represents an ordered sequence of files.
    
    If the frame size exceeds :obj:`fileseq.constants.MAX_FRAME_SIZE`, 
    a ``MaxSizeException`` will be thrown.

    :type sequence: str
    :param sequence: (ie: dir/path.1-100#.ext)
    :raises: :class:`fileseq.exceptions.MaxSizeException`
    """
    def __init__(self, sequence):

        sequence = utils.asString(sequence)

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
            self.setDirname(self._dir)

        self._zfill = self.__class__.getPaddingNum(self._pad)

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
        
        If asking for the inverted range value, and the new inverted range
        exceeded :obj:`fileseq.constants.MAX_FRAME_SIZE`, a ``MaxSizeException``
        will be raised.

        :type template: str
        :rtype: str
        :raises: :class:`fileseq.exceptions.MaxSizeException` 
        """
        # Potentially expensive if inverted range is large
        # and user never asked for it in template
        inverted = (self.invertedFrameRange() or "") if "{inverted}" in template else ""

        return template.format(
            basename=self.basename(),
            extension=self.extension(), start=self.start(),
            end=self.end(), length=len(self),
            padding=self.padding(),
            range=self.frameRange() or "",
            inverted=inverted,
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
        # Make sure the dirname always ends in
        # a path separator character
        sep = utils._getPathSep(dirname)
        if not dirname.endswith(sep):
            dirname += sep

        self._dir = utils.asString(dirname)

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
        self._base = utils.asString(base)

    def padding(self):
        """
        Return the the padding characters in the sequence.

        :rtype: str
        """
        return self._pad

    def setPadding(self, padding):
        """
        Set new padding characters for the sequence.
        i.e. "#" or "@@@" or '%04d', or an empty string to disable range formatting.

        :type padding: str
        :rtype: None
        """
        self._pad = padding
        self._zfill = self.__class__.getPaddingNum(self._pad)

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
        self._ext = utils.asString(ext)

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

        If new inverted range exceeded :obj:`fileseq.constants.MAX_FRAME_SIZE`, 
        a ``MaxSizeException`` will be raised.

        :rtype: str
        :raises: :class:`fileseq.exceptions.MaxSizeException`
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

    def __repr__(self):
        try:
            return "<FileSequence: '%s'>" % str(self)
        except TypeError:
            return super(FileSequence, self).__repr__()

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

        for match in ifilter(None, imap(_check, imap(utils.asString, paths))):
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

    @classmethod
    def findSequencesOnDisk(cls, pattern, include_hidden=False, strictPadding=False):
        """
        Yield the sequences found in the given directory.
        
        Example::
            findSequencesOnDisk('/path/to/files')

        The pattern can also specify glob-like shell wildcards including the following:
            ?         - 1 wildcard character
            *         - 1 or more wildcard character
            {foo,bar} - either 'foo' or 'bar'
        
        Exact frame ranges are not considered, and padding characters are converted to
        wildcards (# or @)

        Example::
            findSequencesOnDisk('/path/to/files/image_stereo_{left,right}.#.jpg')
            findSequencesOnDisk('/path/to/files/imag?_*_{left,right}.@@@.jpg', strictPadding=True)
        
        :param pattern: directory to scan, or pattern to filter in directory
        :type include_hidden: bool
        :param include_hidden: if true, show .hidden files as well
        :type strictPadding: bool
        :param strictPadding: if True, ignore files with padding length different from pattern
        :rtype: list
        """
        # reserve some functions we're going to need quick access to
        _not_hidden = lambda f: not f.startswith('.')
        _match_pattern = None
        _filter_padding = None
        _join = os.path.join

        dirpath, filepat = pattern, None

        # Support the pattern defining a filter for the files
        # in the existing directory
        if not os.path.isdir(pattern):
            dirpath, filepat = os.path.split(pattern)

            if not os.path.isdir(dirpath):
                return []

            # Start building a regex for filtering files
            seq = cls(filepat)
            patt = seq.basename().replace('.', r'\.')
            if seq.padding():
                patt += '\d+'
            if seq.extension():
                patt += seq.extension()

            # Convert braces groups into regex capture groups
            view = bytearray(patt)
            matches = re.finditer(r'{(.*?)(?:,(.*?))*}', patt)
            for match in reversed(list(matches)):
                i, j = match.span()
                view[i:j] = '(%s)' % '|'.join([m.strip() for m in match.groups()])
            view = view.replace('*', '.*')
            view = view.replace('?', '.')
            view += '$'
            print view
            try:
                _match_pattern = re.compile(str(view)).match
            except re.error:
                msg = 'Invalid file pattern: {}'.format(filepat)
                raise FileSeqException(msg)

            if seq.padding() and strictPadding:
                _filter_padding = functools.partial(cls._filterByPaddingNum, num=seq.zfill())

        # Get just the immediate files under the dir.
        # Avoids testing the os.listdir() for files as
        # a second step.
        ret = next(os.walk(dirpath), None)
        files = ret[-1] if ret else []

        # collapse some generators to get us the files that match our regex
        if not include_hidden:
            files = ifilter(_not_hidden, files)

        # Filter by files that match the provided file pattern
        if _match_pattern:
            files = ifilter(_match_pattern, files)

        # Filter by files that match the frame padding in the file pattern
        if _filter_padding:
            # returns a generator
            files = _filter_padding(files)

        # Ensure our dirpath ends with a path separator, so
        # that we can control which sep is used during the 
        # os.path.join
        sep = utils._getPathSep(dirpath)
        if not dirpath.endswith(sep):
            dirpath += sep

        files = (_join(dirpath, f) for f in files)
        files = list(files)

        return list(FileSequence.yield_sequences_in_list(files))

    @classmethod
    def findSequenceOnDisk(cls, pattern, strictPadding=False):
        """
        Search for a specific sequence on disk.

        The padding characters used in the pattern are used to filter the 
        frame values of the files on disk (if strictPadding is True).

        :Example:
            # Find sequence matching basename and extension, and a wildcard for
            # any frame.
            # returns bar.1.exr bar.10.exr, bar.100.exr, bar.1000.exr, inclusive
            >>> findSequenceOnDisk("seq/bar@@@@.exr")

            # Find exactly 4-padded sequence, i.e. seq/bar1-100#.exr
            # returns only frames bar1000.exr through bar9999.exr
            >>> findSequenceOnDisk("seq/bar#.exr", strictPadding=True)

           
        :param pattern: the sequence pattern being searched for
        :rtype: str
        :param strictPadding: if True, ignore files with padding length different from pattern
        :rtype: bool
        :raises: :class:`fileseq.exceptions.FileSeqException` if no sequence is found on disk
        """
        seq = cls(pattern)

        if seq.frameRange() == '' and seq.padding() == '':
            if os.path.isfile(pattern):
                return seq

        patt = seq.format('{dirname}{basename}*{extension}')

        ext = seq.extension()
        basename = seq.basename()
        pad = seq.padding()

        globbed = iglob(patt)
        if pad and strictPadding:
            globbed = cls._filterByPaddingNum(globbed, seq.zfill())

        matches = cls.yield_sequences_in_list(globbed)
        for match in matches:
            if match.basename() == basename and match.extension() == ext:
                return match

        msg = 'no sequence found on disk matching {0}'
        raise FileSeqException(msg.format(pattern))

    @classmethod
    def _filterByPaddingNum(cls, iterable, num):
        """
        Yield only path elements from iterable which have a frame
        padding that matches the given target padding number
        """
        _check = DISK_RE.match

        for item in iterable:
            # Add a filter for paths that don't match the frame
            # padding of a given number
            matches = _check(item)
            if matches:
                actualNum = len(matches.group(3))
                if actualNum != num:
                    continue
            
            yield item

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
        match = PRINTF_SYNTAX_PADDING_RE.match(chars)
        if match:
            return int(match.group(1))

        try:
            return sum([PAD_MAP[char] for char in chars])
        except KeyError:
            msg = "Detected an unsupported padding character: \"{}\"."
            msg += " Supported padding characters: {} or printf syntax padding"
            msg += " %<int>d"
            raise ValueError(msg.format(char, str(PAD_MAP.keys())))
