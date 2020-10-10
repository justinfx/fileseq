#! /usr/bin/env python
"""
filesequence - A parsing object representing sequential files for fileseq.
"""
from __future__ import absolute_import

from builtins import next
from builtins import filter
from builtins import str
from builtins import map
from builtins import object

import future.utils as futils
from future.utils import iteritems

import os
import re
import decimal
import functools
from glob import iglob

from fileseq.exceptions import ParseException, MaxSizeException, FileSeqException
from fileseq.constants import \
    PAD_STYLE_DEFAULT, PAD_STYLE_HASH1, PAD_STYLE_HASH4, PAD_MAP, \
    DISK_RE, DISK_SUB_RE, SPLIT_RE, SPLIT_SUB_RE, \
    PRINTF_SYNTAX_PADDING_RE, HOUDINI_SYNTAX_PADDING_RE
from fileseq.frameset import FrameSet
from fileseq import utils


class FileSequence(object):
    """:class:`FileSequence` represents an ordered sequence of files.

        Args:
            sequence (str): (ie: dir/path.1-100#.ext)

        Returns:
            :class:`FileSequence`:

        Raises:
            :class:`fileseq.exceptions.MaxSizeException`: If frame size exceeds
            ``fileseq.constants.MAX_FRAME_SIZE``
    """
    DISK_RE = DISK_RE
    DISK_SUB_RE = DISK_SUB_RE
    PAD_MAP = PAD_MAP
    SPLIT_RE = SPLIT_RE
    SPLIT_SUB_RE = SPLIT_SUB_RE

    def __init__(self, sequence, pad_style=PAD_STYLE_DEFAULT, allow_subframes=False):
        """Init the class
        """
        sequence = utils.asString(sequence)

        if not hasattr(self, '_frameSet'):

            self._frameSet = None

            if allow_subframes:
                split_re = self.SPLIT_SUB_RE
                disk_re = self.DISK_SUB_RE
            else:
                split_re = self.SPLIT_RE
                disk_re = self.DISK_RE

            try:
                # the main case, padding characters in the path.1-100#.exr
                path, frames, self._pad, self._ext = split_re.split(sequence, 1)
                self._frame_pad, _, self._subframe_pad = self._pad.partition('.')
                self._dir, self._base = os.path.split(path)
                self._frameSet = FrameSet(frames)
            except ValueError:
                # edge case 1; we've got an invalid pad
                for placeholder in self.PAD_MAP:
                    if placeholder in sequence:
                        msg = "Failed to parse FileSequence: {0}"
                        raise ParseException(msg.format(sequence))
                # edge case 2; we've got a single frame of a sequence
                a_frame = disk_re.match(sequence)
                if a_frame:
                    self._dir, self._base, frames, self._ext = a_frame.groups()
                    # edge case 3: we've got a single versioned file, not a sequence
                    if frames and not self._base.endswith('.'):
                        self._base = self._base + frames
                        self._pad = ''
                        self._frame_pad = ''
                        self._subframe_pad = ''
                    elif not frames:
                        self._pad = ''
                        self._frame_pad = ''
                        self._subframe_pad = ''
                        self._frameSet = None
                    else:
                        self._frameSet = FrameSet(frames)
                        if self._frameSet:
                            frame_num, _, subframe_num = frames.partition('.')
                            self._frame_pad = self.getPaddingChars(len(frame_num), pad_style=pad_style)
                            if subframe_num:
                                self._subframe_pad = self.getPaddingChars(len(subframe_num), pad_style=pad_style)
                                self._pad = '.'.join([self._frame_pad, self._subframe_pad])
                            else:
                                self._pad = self._frame_pad
                                self._subframe_pad = ''
                        else:
                            self._pad = ''
                            self._frame_pad = ''
                            self._subframe_pad = ''
                            self._frameSet = None
                # edge case 4; we've got a solitary file, not a sequence
                else:
                    path, self._ext = os.path.splitext(sequence)
                    self._dir, self._base = os.path.split(path)
                    self._pad = ''
                    self._frame_pad = ''
                    self._subframe_pad = ''

        if self._dir:
            self.setDirname(self._dir)

        self._pad_style = pad_style
        self._zfill = self.getPaddingNum(self._frame_pad, pad_style=pad_style)
        self._decimal_places = self.getPaddingNum(self._subframe_pad, pad_style=pad_style)

        # Round subframes to match sequence
        if self._frameSet is not None and self._frameSet.hasSubFrames():
            self._frameSet = FrameSet([
                utils.quantize(frame, self._decimal_places)
                for frame in self._frameSet
            ])

    def copy(self):
        """
        Create a deep copy of this sequence

        Returns:
            :class:`.FileSequence`:
        """
        fs = self.__class__.__new__(self.__class__)
        fs.__dict__ = self.__dict__.copy()
        fs._frameSet = None
        if self._frameSet is not None:
            fs._frameSet = self._frameSet.copy()
        return fs

    def format(self, template="{basename}{range}{padding}{extension}"):
        """Return the file sequence as a formatted string according to
        the given template.

        Utilizes the python string format syntax.  Available keys include:
            * basename - the basename of the sequence.
            * range - the range of the sequence
            * padding - the detecting amount of padding.
            * extension - the file extension of the sequence.
            * start - the start frame.
            * end - the end frame.
            * length - the length of the frame range.
            * inverted - the inverted frame range. (returns "" if none)
            * dirname - the directory name.

        If asking for the inverted range value, and the new inverted range
        exceeded ``fileseq.constants.MAX_FRAME_SIZE``, a ``MaxSizeException``
        will be raised.

        Args:
            template (str):

        Returns:
            str:

        Raises:
            :class:`fileseq.exceptions.MaxSizeException`: If frame size exceeds
            `fileseq.constants.MAX_FRAME_SIZE``
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

        Returns:
            list[:class:`FileSequence`]:
        """
        result = []
        for frange in self.frameRange().split(","):
            result.append(self.__class__(''.join(
                (self._dir, self._base, frange, self._pad, self._ext))))
        return result

    def dirname(self):
        """
        Return the directory name of the sequence.

        Returns:
            str:
        """
        return self._dir

    def setDirname(self, dirname):
        """
        Set a new directory name for the sequence.

        Args:
            dirname (str): the new directory name
        """
        # Make sure the dirname always ends in
        # a path separator character
        dirname = utils.asString(dirname)
        sep = utils._getPathSep(dirname)
        if not dirname.endswith(sep):
            dirname = futils.native_str(dirname) + sep

        self._dir = dirname

    def basename(self):
        """
        Return the basename of the sequence.

        Returns:
            str: sequence basename
        """
        return self._base

    def setBasename(self, base):
        """
        Set a new basename for the sequence.

        Args:
            base (str): the new base name
        """
        self._base = utils.asString(base)

    def padStyle(self):
        """
        Return the the padding style of the sequence.
        See fileseq.PAD_STYLE_HASH1 and fileseq.PAD_STYLE_HASH4

        Returns:
            (PAD_STYLE_DEFAULT or PAD_STYLE_HASH1 or PAD_STYLE_HASH4): padding style
        """
        return self._pad_style

    def setPadStyle(self, pad_style):
        """
        Set new padding style for the sequence.
        See fileseq.PAD_STYLE_HASH1 and fileseq.PAD_STYLE_HASH4

        Args:
            pad_style (PAD_STYLE_DEFAULT or PAD_STYLE_HASH1 or PAD_STYLE_HASH4): padding style to set
        """
        self._pad_style = pad_style
        self._frame_pad = self.getPaddingChars(self._zfill, pad_style=pad_style)
        if self._decimal_places:
            self._subframe_pad = self.getPaddingChars(
                self._decimal_places, pad_style=self._pad_style
            )
            self._pad = '.'.join([self._frame_pad, self._subframe_pad])
        else:
            self._pad = self._frame_pad
            self._subframe_pad = ''

    def padding(self):
        """
        Return the the padding characters in the sequence.

        Returns:
            str: sequence padding
        """
        return self._pad

    def setPadding(self, padding):
        """
        Set new padding characters for the sequence.
        i.e. "#" or "@@@" or '%04d', or an empty string to disable range formatting.

        Args:
            padding (str): sequence padding to set
        """
        self._pad = padding
        self._frame_pad, _, self._subframe_pad = self._pad.partition('.')
        self._zfill = self.getPaddingNum(self._frame_pad, pad_style=self._pad_style)
        self._decimal_places = self.getPaddingNum(self._subframe_pad, pad_style=self._pad_style)

    def framePadding(self):
        """
        Return the the padding characters in the sequence.

        Returns:
            str: sequence padding
        """
        return self._frame_pad

    def setFramePadding(self, padding):
        """
        Set new padding characters for the frames of the sequence.
        i.e. "#" or "@@@" or '%04d', or an empty string to disable range formatting.

        Args:
            padding (str): sequence padding to set
        """
        self._frame_pad = padding
        if self._subframe_pad:
            self._pad = '.'.join([self._frame_pad, self._subframe_pad])
        else:
            self._pad = self._frame_pad
        self._zfill = self.getPaddingNum(self._frame_pad, pad_style=self._pad_style)

    def subframePadding(self):
        """
        Return the the padding characters for subframes in the sequence.

        Returns:
            str: sequence padding
        """
        return self._subframe_pad

    def setSubframePadding(self, padding):
        """
        Set new padding characters for the subframes in the sequence.
        i.e. "#" or "@@@", or an empty string to disable range
        formatting.

        Args:
            padding (str): sequence padding to set
        """
        self._subframe_pad = padding
        if self._subframe_pad:
            self._pad = '.'.join([self._frame_pad, self._subframe_pad])
        else:
            self._pad = self._frame_pad
        self._decimal_places = self.getPaddingNum(self._subframe_pad, pad_style=self._pad_style)

    def frameSet(self):
        """
        Return the :class:`.FrameSet` of the sequence if specified,
        otherwise None.

        Returns:
            :class:`.FrameSet` or None:
        """
        return self._frameSet

    def setFrameSet(self, frameSet):
        """
        Set a new :class:`.FrameSet` for the sequence.

        Args:
            frameSet (:class:`.FrameSet`): the new :class:`.FrameSet` object
        """
        if frameSet is not None and frameSet.hasSubFrames():
            if all(isinstance(frame, decimal.Decimal) for frame in frameSet):
                frameSet = FrameSet([
                    utils.quantize(frame, self._decimal_places)
                    for frame in frameSet
                ])
        self._frameSet = frameSet

    def extension(self):
        """
        Return the file extension of the sequence, including leading period.

        Returns:
            str:
        """
        return self._ext

    def setExtension(self, ext):
        """
        Set a new file extension for the sequence.

        Note:
            A leading period will be added if none is provided.

        Args:
            ext (str): the new file extension
        """
        if ext[0] != ".":
            ext = "." + ext
        self._ext = utils.asString(ext)

    def setExtention(self, ext):
        """
        Deprecated: use :meth:`setExtension`.

        Args:
            ext (str):
        """
        import warnings
        msg = "the setExtention method is deprecated, please use setExtension"
        warnings.warn(msg)
        self.setExtension(ext)

    def frameRange(self):
        """
        Returns the string formatted frame range of the sequence.
        Will return an empty string if the sequence has no frame pattern.

        Returns:
            str:
        """
        if not self._frameSet:
            return ''
        return self._frameSet.frameRange(self._zfill, self._decimal_places)

    def setFrameRange(self, frange):
        """
        Set a new frame range for the sequence.

        Args:
            frange (str): a properly formatted frame range, as per :class:`.FrameSet`
        """
        self._frameSet = FrameSet(frange)

    def invertedFrameRange(self):
        """
        Returns the inverse string formatted frame range of the sequence.
        Will return an empty string if the sequence has no frame pattern,
        or the frame range includes subframes.

        Returns:
            str:

        Raises:
            :class:`fileseq.exceptions.MaxSizeException`: If new inverted range
                exceeded ``fileseq.constants.MAX_FRAME_SIZE``
        """
        if not self._frameSet or self._frameSet.hasSubFrames():
            return ''
        return self._frameSet.invertedFrameRange(self._zfill)

    def start(self):
        """
        Returns the start frame of the sequence's :class:`.FrameSet`.
        Will return 0 if the sequence has no frame pattern.

        Returns:
            int:
        """
        if not self._frameSet:
            return 0
        return self._frameSet.start()

    def end(self):
        """
        Returns the end frame of the sequences :class:`.FrameSet`.
        Will return 0 if the sequence has no frame pattern.

        Returns:
            int:
        """
        if not self._frameSet:
            return 0
        return self._frameSet.end()

    def zfill(self):
        """
        Returns the zfill depth (ie the number of zeroes to pad with).

        Returns:
            int:
        """
        return self._zfill

    def decimalPlaces(self):
        """
        Returns the number of decimal places to output.

        Returns:
            int or None:
        """
        return self._decimal_places

    def frame(self, frame):
        """
        Return a path for the given frame in the sequence.  Numeric values or
        numeric strings are treated as a frame number and padding is applied,
        all other values are passed though.

        Examples:
            >>> seq = FileSequence('/foo/bar.1-10#.exr')
            >>> seq.frame(1)
            '/foo/bar.0001.exr'
            >>> seq.frame("#")
            '/foo/bar.#.exr'

        Args:
            frame (int, float, decimal.Decimal or str): the desired frame number
                or a char to pass through (ie. #)

        Returns:
            str:
        """
        if self._zfill == 0:
            # There may have been no placeholder for frame IDs in
            # the sequence, in which case we don't want to insert
            # a frame ID
            zframe = ""
        else:
            zframe = None
            if not isinstance(frame, futils.integer_types + (float, decimal.Decimal)):
                try:
                    frame = int(frame)
                except ValueError:
                    try:
                        frame = decimal.Decimal(frame)
                    except decimal.DecimalException:
                        zframe = frame
            if zframe is None:
                zframe = utils.pad(frame, self._zfill, self._decimal_places)

        return futils.native_str("".join((self._dir, self._base, zframe, self._ext)))

    def index(self, idx):
        """
        Return the path to the file at the given index.

        Args:
            idx (int): the desired index

        Returns:
            str:
        """
        return self.__getitem__(idx)

    def __iter__(self):
        """
        Allow iteration over the path or paths this :class:`FileSequence`
        represents.

        Yields:
            :class:`FileSequence`:
        """
        # If there is no frame range, or there is no padding
        # characters, then we only want to represent a single path
        if not self._frameSet or not self._zfill:
            yield utils.asString(self)
            return

        for f in self._frameSet:
            yield self.frame(f)

    def __getitem__(self, idx):
        """
        Allows indexing and slicing into the underlying :class:`.FrameSet`

        When indexing, a string filepath is returns for the frame.

        When slicing, a new :class:`FileSequence` is returned.
        Slicing outside the range of the sequence results in an
        IndexError

        Args:
            idx (int or slice): the desired index

        Returns:
            str or :obj:`FileSequence`:

        Raises:
            :class:`IndexError`: If slice is outside the range of the sequence
        """
        if not self._frameSet:
            return futils.native_str(self)

        frames = self._frameSet[idx]

        if not hasattr(idx, 'start'):
            return self.frame(frames)

        fset = FrameSet(frames)
        if fset.is_null:
            raise IndexError("slice is out of range and returns no frames")

        fs = self.copy()
        fs.setFrameSet(fset)
        return fs

    def __len__(self):
        """
        The length (number of files) represented by this :class:`FileSequence`.

        Returns:
            int:
        """
        if not self._frameSet or not self._zfill:
            return 1
        return len(self._frameSet)

    def __str__(self):
        """
        String representation of this :class:`FileSequence`.

        Returns:
            str:
        """
        frameSet = utils.asString(self._frameSet or "")
        return "".join((
            self._dir,
            self._base,
            frameSet,
            self._pad if frameSet else "",
            self._ext))

    def __repr__(self):
        try:
            return "<%s: '%s'>" % (self.__class__.__name__, str(self))
        except TypeError:
            return super(self.__class__, self).__repr__()

    def __eq__(self, other):
        return str(self) == str(other)

    def __ne__(self, other):
        return str(self) != str(other)

    def __hash__(self):
        # TODO: Technically we should be returning None,
        # as this class is mutable and cannot reliably be hashed.
        # Python2 allows it without this definition.
        # Python3 fails with TypeError: unhashable.
        # For now, preserving the hashing behaviour in py3.
        return id(self)

    @classmethod
    def yield_sequences_in_list(
        cls, paths, using=None, pad_style=PAD_STYLE_DEFAULT, allow_subframes=False
    ):
        """
        Yield the discrete sequences within paths.  This does not try to
        determine if the files actually exist on disk, it assumes you already
        know that.

        A template :obj:`FileSequence` object can also be provided via the
        ``using`` parameter. Given this template, the dirname, basename, and
        extension values will be used to extract the frame value from the paths
        instead of parsing each path from scratch.

        Examples:
            The ``using`` field can supply a template for extracting the frame
            component from the paths::

                paths = [
                    '/dir/file_001.0001.ext',
                    '/dir/file_002.0001.ext',
                    '/dir/file_003.0001.ext',
                ]
                template = FileSequence('/dir/file_#.0001.ext')
                seqs = FileSequence.yield_sequences_in_list(paths, using)
                # [<FileSequence: '/dir/file_1-3@@@.0001.ext'>]

        Args:
            paths (list[str]): a list of paths
            using (:obj:`FileSequence`): Optional sequence to use as template
            pad_style (PAD_STYLE_DEFAULT or PAD_STYLE_HASH1 or PAD_STYLE_HASH4): padding style
            allow_subframes (bool): if True, handle subframe filenames

        Yields:
            :obj:`FileSequence`:
        """
        seqs = {}
        if allow_subframes:
            _check = cls.DISK_SUB_RE.match
        else:
            _check = cls.DISK_RE.match

        using_template = isinstance(using, FileSequence)

        if using_template:
            dirname, basename, ext = using.dirname(), using.basename(), using.extension()
            head = len(dirname + basename)
            tail = -len(ext)
            frames = set()

            for path in filter(None, map(utils.asString, paths)):
                frame = path[head:tail]
                frame, _, subframe = frame.partition(".")
                key = (dirname, basename, ext, len(subframe))
                try:
                    int(frame)
                except ValueError:
                    try:
                        decimal.Decimal(frame)
                    except decimal.DecimalException:
                        continue
                seqs.setdefault(key, frames).add(frame)

        else:
            for match in filter(None, map(_check, map(utils.asString, paths))):
                dirname, basename, frame, ext = match.groups()
                if not basename and not ext:
                    continue
                if frame:
                    _, _, subframe = frame.partition(".")
                    key = (dirname, basename, ext, len(subframe))
                else:
                    key = (dirname, basename, ext, 0)
                seqs.setdefault(key, set())
                if frame:
                    seqs[key].add(frame)

        for (dirname, basename, ext, decimal_places), frames in iteritems(seqs):
            # build the FileSequence behind the scenes, rather than dupe work
            seq = cls.__new__(cls)
            seq._dir = dirname or ''
            seq._base = basename or ''
            seq._ext = ext or ''
            seq._pad_style = pad_style
            if frames:
                seq._frameSet = FrameSet(frames)

                frame_lengths = set()
                for frame in frames:
                    frame_num, _, _ = frame.partition(".")
                    frame_lengths.add(len(frame_num))

                seq._frame_pad = cls.getPaddingChars(min(frame_lengths), pad_style=pad_style)
                if decimal_places:
                    seq._subframe_pad = cls.getPaddingChars(decimal_places, pad_style=pad_style)
                else:
                    seq._subframe_pad = ''
            else:
                seq._frameSet = None
                seq._frame_pad = ''
                seq._subframe_pad = ''

            if seq._subframe_pad:
                seq._pad = '.'.join([seq._frame_pad, seq._subframe_pad])
            else:
                seq._pad = seq._frame_pad

            seq.__init__(utils.asString(seq))
            yield seq

    @classmethod
    def findSequencesInList(cls, paths, pad_style=PAD_STYLE_DEFAULT, allow_subframes=False):
        """
        Returns the list of discrete sequences within paths.  This does not try
        to determine if the files actually exist on disk, it assumes you
        already know that.

        Args:
            paths (list[str]): a list of paths
            pad_style (PAD_STYLE_DEFAULT or PAD_STYLE_HASH1 or PAD_STYLE_HASH4): padding style
            allow_subframes (bool): if True, handle subframe filenames

        Returns:
            list:
        """
        return list(
            cls.yield_sequences_in_list(paths, pad_style=pad_style, allow_subframes=allow_subframes)
        )

    @classmethod
    def findSequencesOnDisk(
        cls, pattern, include_hidden=False, strictPadding=False, pad_style=PAD_STYLE_DEFAULT,
        allow_subframes=False
    ):
        """
        Yield the sequences found in the given directory.

        Examples::

            FileSequence.findSequencesOnDisk('/path/to/files')

        The `pattern` can also specify glob-like shell wildcards including the following:
            * ``?``         - 1 wildcard character
            * ``*``         - 1 or more wildcard character
            * ``{foo,bar}`` - either 'foo' or 'bar'

        Exact frame ranges are not considered, and padding characters are converted to
        wildcards (``#`` or ``@``)

        Examples::

            FileSequence.findSequencesOnDisk('/path/to/files/image_stereo_{left,right}.#.jpg')
            FileSequence.findSequencesOnDisk('/path/to/files/imag?_*_{left,right}.@@@.jpg', strictPadding=True)

        Args:
            pattern (str): directory to scan, or pattern to filter in directory
            include_hidden (bool): if true, show .hidden files as well
            strictPadding (bool): if True, ignore files with padding length different from pattern
            pad_style (PAD_STYLE_DEFAULT or PAD_STYLE_HASH1 or PAD_STYLE_HASH4): padding style
            allow_subframes (bool): if True, handle subframe filenames

        Returns:
            list:
        """
        # reserve some functions we're going to need quick access to
        _not_hidden = lambda f: not f.startswith('.')
        _match_pattern = None
        _filter_padding = None
        _join = os.path.join

        seq = None
        dirpath = pattern

        # Support the pattern defining a filter for the files
        # in the existing directory
        if not os.path.isdir(pattern):
            dirpath, filepat = os.path.split(pattern)

            if not os.path.isdir(dirpath):
                return []

            # Start building a regex for filtering files
            seq = cls(filepat, pad_style=pad_style, allow_subframes=allow_subframes)
            patt = r'\A'
            patt += cls._globCharsToRegex(seq.basename())
            if seq.padding():
                patt += '('
                if seq.framePadding():
                    patt += r'\d+'
                    if seq.subframePadding():
                        patt += r'\.\d+'
                patt += ')'
            if seq.extension():
                patt += cls._globCharsToRegex(seq.extension())

            # Convert braces groups into regex capture groups
            matches = re.finditer(r'{(.*?)(?:,(.*?))*}', patt)
            for match in reversed(list(matches)):
                i, j = match.span()
                regex = '(?:%s)' % '|'.join([m.strip() for m in match.groups()])
                patt = "".join((patt[0:i], regex, patt[j:]))
            patt += r'\Z'
            try:
                _match_pattern = re.compile(patt).match
            except re.error:
                msg = 'Invalid file pattern: {}'.format(filepat)
                raise FileSeqException(msg)

            if seq.padding() and strictPadding:
                get_frame = lambda f: _match_pattern(f).group(1)
                _filter_padding = functools.partial(
                    cls._filterByPaddingNum,
                    zfill=seq.zfill(),
                    decimal_places=seq.decimalPlaces(),
                    get_frame=get_frame
                )

        # Get just the immediate files under the dir.
        # Avoids testing the os.listdir() for files as
        # a second step.
        ret = next(os.walk(dirpath), None)
        files = ret[-1] if ret else []

        # collapse some generators to get us the files that match our regex
        if not include_hidden:
            files = filter(_not_hidden, files)

        # Filter by files that match the provided file pattern
        if _match_pattern:
            files = filter(_match_pattern, files)

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

        files = [_join(dirpath, f) for f in files]

        seqs = list(
            cls.yield_sequences_in_list(files, pad_style=pad_style, allow_subframes=allow_subframes)
        )

        if _filter_padding and seq:
            frame_pad = cls.conformPadding(seq.framePadding(), pad_style=pad_style)
            subframe_pad = cls.conformPadding(seq.subframePadding(), pad_style=pad_style)
            # strict padding should preserve the original padding
            # characters in the found sequences.
            for s in seqs:
                s.setFramePadding(frame_pad)
                s.setSubframePadding(subframe_pad)

        return seqs

    @classmethod
    def findSequenceOnDisk(cls, pattern, strictPadding=False, pad_style=PAD_STYLE_DEFAULT):
        """
        Search for a specific sequence on disk.

        The padding characters used in the `pattern` are used to filter the
        frame values of the files on disk (if `strictPadding` is True).

        Examples:
            Find sequence matching basename and extension, and a wildcard for
            any frame.
            returns bar.1.exr bar.10.exr, bar.100.exr, bar.1000.exr, inclusive

            ``FileSequence.findSequenceOnDisk("seq/bar@@@@.exr")``

            Find exactly 4-padded sequence, i.e. seq/bar1-100#.exr
            returns only frames bar1000.exr through bar9999.exr

            ``FileSequence.findSequenceOnDisk("seq/bar#.exr", strictPadding=True)``

        Args:
            pattern (str): the sequence pattern being searched for
            strictPadding (bool): if True, ignore files with padding length different from `pattern`
            pad_style (PAD_STYLE_DEFAULT or PAD_STYLE_HASH1 or PAD_STYLE_HASH4): padding style

        Returns:
            str:

        Raises:
            :class:`.FileSeqException`: if no sequence is found on disk
        """
        seq = cls(pattern, allow_subframes=True, pad_style=pad_style)

        if seq.frameRange() == '' and seq.padding() == '':
            if os.path.isfile(pattern):
                return seq

        patt = seq.format('{dirname}{basename}*{extension}')

        dirname = seq.dirname()
        basename = seq.basename()
        ext = seq.extension()
        pad = seq.padding()
        frame_pad = seq.framePadding()
        subframe_pad = seq.subframePadding()

        globbed = iglob(patt)
        if pad:
            patt = r'\A'
            if dirname:
                patt = r'.*[/\\]'
            patt += re.escape(basename) + '(.*)' + re.escape(ext) + r'\Z'
            get_frame = lambda f: re.match(patt, f).group(1)

            if strictPadding:
                globbed = cls._filterByPaddingNum(
                    globbed,
                    seq.zfill(),
                    decimal_places=seq.decimalPlaces(),
                    get_frame=get_frame
                )
                frame_pad = cls.conformPadding(frame_pad, pad_style=pad_style)
                subframe_pad = cls.conformPadding(subframe_pad, pad_style=pad_style)
            else:
                globbed = cls._filterByPaddingNum(
                    globbed,
                    None,
                    decimal_places=seq.decimalPlaces(),
                    get_frame=get_frame
                )

        sequences = []
        allow_subframes = bool(seq.decimalPlaces())
        for match in cls.yield_sequences_in_list(
            globbed, using=seq, pad_style=pad_style, allow_subframes=allow_subframes
        ):
            if match.basename() == basename and match.extension() == ext:
                if pad and strictPadding:
                    match.setFramePadding(frame_pad)
                    match.setSubframePadding(subframe_pad)
                sequences.append(match)

        if len(sequences) == 1:
            return sequences[0]
        elif not sequences:
            msg = 'no sequence found on disk matching {0}'
        else:
            msg = 'multiple sequences found on disk matching {0}'
        raise FileSeqException(msg.format(pattern))

    @staticmethod
    def _globCharsToRegex(filename):
        """
        Translate single character elements of a shell pattern to make suitable
        for a regular expression pattern

        Args:
            filename (str): filename containing shell pattern to convert

        Returns:
            str:
        """
        filename = filename.replace('.', r'\.')
        filename = filename.replace('*', '.*')
        filename = filename.replace('?', '.')
        return filename

    @classmethod
    def _filterByPaddingNum(cls, iterable, zfill, decimal_places=0, get_frame=None):
        """
        Yield only path elements from iterable which have a frame padding that
        matches the given target padding numbers. If zfill is None only the
        subframe length is matched against decimal places. If provided get_frame
        should be a callable taking one argument that will extract the frame
        number from a filename.

        Args:
            iterable (collections.Iterable):
            zfill (int or None):
            decimal_places (int):
            get_frame (callable):

        Yields:
            str:
        """
        if decimal_places == 0:
            _check = cls.DISK_RE.match
        else:
            _check = cls.DISK_SUB_RE.match

        for item in iterable:
            # Add a filter for paths that don't match the frame
            # padding of a given number
            matches = _check(item)
            if not matches:
                if zfill is None or zfill <= 0:
                    # Not a sequence pattern, but we were asked
                    # to match on a zero padding
                    yield item

                continue

            # Ensure DISK_RE matches before calling optional get_frame function
            frame = matches.group(3) or ''
            if frame and get_frame is not None:
                frame = get_frame(item) or ''

            if not frame:
                if zfill is None or zfill <= 0:
                    # No frame value was parsed, but we were asked
                    # to match on a zero padding
                    yield item
                continue

            # We have a frame number
            frame, _, subframe = frame.partition(".")
            if len(subframe) != decimal_places:
                continue

            if zfill is None:
                yield item
                continue

            if frame[0] == '0' or frame[:2] == '-0':
                if len(frame) == zfill:
                    # A frame leading with '0' is explicitly
                    # padded and can only be a match if its exactly
                    # the target padding number
                    yield item
                continue

            if len(frame) >= zfill:
                # A frame that does not lead with '0' can match
                # a padding width >= to the target padding number
                yield item
                continue

    @staticmethod
    def getPaddingChars(num, pad_style=PAD_STYLE_DEFAULT):
        """
        Given a particular amount of padding, return the proper padding characters.

        Args:
            num (int): required width of string with padding
            pad_style (PAD_STYLE_DEFAULT or PAD_STYLE_HASH1 or PAD_STYLE_HASH4): padding style

        Returns:
            str:
        """
        if pad_style is PAD_STYLE_HASH1:
            return "#" * max(1, num)
        elif pad_style is PAD_STYLE_HASH4:
            if num == 0:
                return "@"
            if num % 4 == 0:
                return "#" * (num // 4)
            else:
                return "@" * num

    @classmethod
    def getPaddingNum(cls, chars, pad_style=PAD_STYLE_DEFAULT):
        """
        Given a supported group of padding characters, return the amount of padding.

        Args:
            chars (str): a supported group of padding characters
            pad_style (PAD_STYLE_DEFAULT or PAD_STYLE_HASH1 or PAD_STYLE_HASH4): padding style

        Returns:
            int:

        Raises:
            ValueError: if unsupported padding character is detected
        """
        if not chars:
            return 0

        match = PRINTF_SYNTAX_PADDING_RE.match(chars) or HOUDINI_SYNTAX_PADDING_RE.match(chars)
        if match:
            paddingNumStr = match.group(1)
            paddingNum = int(paddingNumStr) if paddingNumStr else 1
            return max(paddingNum, 1)

        try:
            rval = 0
            for char in chars:
                rval += cls.PAD_MAP[char][pad_style]
            return rval
        except KeyError:
            msg = "Detected an unsupported padding character: \"{}\"."
            msg += " Supported padding characters: {} or printf syntax padding"
            msg += " %<int>d"
            raise ValueError(msg.format(char, utils.asString(list(cls.PAD_MAP))))

    @classmethod
    def conformPadding(cls, chars, pad_style=PAD_STYLE_DEFAULT):
        """
        Ensure alternate input padding formats are conformed
        to formats defined in PAD_MAP

        If chars is already a format defined in PAD_MAP, then
        it is returned unmodified.

        Example::
            '#'    -> '#'
            '@@@@' -> '@@@@'
            '%04d' -> '#'

        Args:
            chars (str): input padding chars
            pad_style (PAD_STYLE_DEFAULT or PAD_STYLE_HASH1 or PAD_STYLE_HASH4): padding style

        Returns:
            str: conformed padding chars

        Raises:
            ValueError: If chars contains invalid padding characters
        """
        pad = chars
        if pad and pad[0] not in cls.PAD_MAP:
            num = cls.getPaddingNum(pad, pad_style=pad_style)
            pad = cls.getPaddingChars(num, pad_style=pad_style)
        return pad
