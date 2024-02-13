"""
filesequence - A parsing object representing sequential files for fileseq.
"""
from __future__ import annotations

import decimal
import fnmatch
import functools
import operator
import os
import re
import sys
import typing
from glob import iglob
from typing_extensions import Self

from . import constants, utils
from .constants import (
    PAD_STYLE_DEFAULT, PAD_MAP, REVERSE_PAD_MAP,
    DISK_RE, DISK_SUB_RE, SPLIT_RE, SPLIT_SUB_RE,
    PRINTF_SYNTAX_PADDING_RE, HOUDINI_SYNTAX_PADDING_RE,
    UDIM_PADDING_PATTERNS)
from .exceptions import ParseException, FileSeqException
from .frameset import FrameSet


class FileSequence:
    """:class:`FileSequence` represents an ordered sequence of files.

        Args:
            sequence (str): (ie: dir/path.1-100#.ext)

        Returns:
            :class:`FileSequence`:

        Raises:
            :class:`fileseq.exceptions.MaxSizeException`: If frame size exceeds
            ``fileseq.constants.MAX_FRAME_SIZE``
    """
    _base: str
    _decimal_places: int
    _dir: str
    _ext: str
    _frameSet: FrameSet|None
    _frame_pad: str
    _pad: str
    _subframe_pad: str
    
    DISK_RE = DISK_RE
    DISK_SUB_RE = DISK_SUB_RE
    PAD_MAP = PAD_MAP
    REVERSE_PAD_MAP = REVERSE_PAD_MAP
    SPLIT_RE = SPLIT_RE
    SPLIT_SUB_RE = SPLIT_SUB_RE

    _DEFAULT_PAD_CHAR = '@'

    def __init__(self,
                 sequence: str,
                 pad_style: constants._PadStyle = PAD_STYLE_DEFAULT,
                 allow_subframes: bool = False):
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
                        msg = "Failed to parse FileSequence: {!r}"
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

    def copy(self) -> Self:
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

    def format(self, template="{basename}{range}{padding}{extension}") -> str:
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
        try:
            return self._format(template)
        except UnicodeEncodeError:
            return self._format(str(template))

    def _format(self, template):
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

    def split(self) -> list[Self]:
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

    def dirname(self) -> str:
        """
        Return the directory name of the sequence.

        Returns:
            str:
        """
        return self._dir

    def setDirname(self, dirname: str):
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
            dirname = str(dirname) + sep

        self._dir = dirname

    def basename(self) -> str:
        """
        Return the basename of the sequence.

        Returns:
            str: sequence basename
        """
        return self._base

    def setBasename(self, base: str):
        """
        Set a new basename for the sequence.

        Args:
            base (str): the new base name
        """
        self._base = utils.asString(base)

    def padStyle(self) -> constants._PadStyle:
        """
        Return the padding style of the sequence.
        See fileseq.constants.PAD_STYLE_HASH1 and fileseq.constants.PAD_STYLE_HASH4

        Returns:
            (`PAD_STYLE_DEFAULT` or `PAD_STYLE_HASH1` or `PAD_STYLE_HASH4`): padding style
        """
        return self._pad_style

    def setPadStyle(self, pad_style: constants._PadStyle, set_zfill: bool = False):
        """
        Set new padding style for the sequence.
        See fileseq.constants.PAD_STYLE_HASH1 and fileseq.constants.PAD_STYLE_HASH4

        The default behavior converts only the padding characters representation per the new style,
        the same zfill/decimalPlaces value. If ``set_zfill=True``, convert the zfill/decimalPlaces
        values to match the meaning of the padding characters per the new style.

        Args:
            pad_style (`PAD_STYLE_DEFAULT` or `PAD_STYLE_HASH1` or `PAD_STYLE_HASH4`): padding style to set
            set_zfill (bool): If True, convert zfill/decimalPlaces value instead of padding chars
        """
        if set_zfill:
            zfill = self.getPaddingNum(self._frame_pad, pad_style=pad_style)
            decimal_places = self.getPaddingNum(self._subframe_pad, pad_style=pad_style)

            self._pad_style = pad_style
            self._zfill = zfill
            self._decimal_places = decimal_places
            return

        decimal_places = self._decimal_places
        frame_pad = self.getPaddingChars(self._zfill, pad_style=pad_style)
        if decimal_places:
            subframe_pad = self.getPaddingChars(decimal_places, pad_style=pad_style)
            pad = '.'.join([frame_pad, subframe_pad])
        else:
            subframe_pad = ''
            pad = frame_pad

        self._pad_style = pad_style
        self._pad = pad
        self._frame_pad = frame_pad
        self._subframe_pad = subframe_pad

    def padding(self) -> str:
        """
        Return the padding characters in the sequence.

        Returns:
            str: sequence padding
        """
        return self._pad

    def setPadding(self, padding: str):
        """
        Set new padding characters for the sequence.
        i.e. "#" or "@@@" or '%04d', or an empty string to disable range formatting.

        Args:
            padding (str): sequence padding to set

        Raises:
            ValueError: if unrecognized padding characters are provided
        """
        pad_style = self._pad_style

        frame_pad, _, subframe_pad = padding.partition('.')
        zfill = self.getPaddingNum(frame_pad, pad_style=pad_style)
        decimal_places = self.getPaddingNum(subframe_pad, pad_style=pad_style)

        # Set all fields atomically after parsing valid padding characters
        self._pad = padding
        self._frame_pad = frame_pad
        self._subframe_pad = subframe_pad
        self._zfill = zfill
        self._decimal_places = decimal_places

    def framePadding(self) -> str:
        """
        Return the padding characters in the sequence.

        Returns:
            str: sequence padding
        """
        return self._frame_pad

    def setFramePadding(self, padding: str):
        """
        Set new padding characters for the frames of the sequence.
        i.e. "#" or "@@@" or '%04d', or an empty string to disable range formatting.

        Args:
            padding (str): sequence padding to set

        Raises:
            ValueError: if unrecognized padding characters are provided
        """
        subframe_pad = self._subframe_pad
        pad_style = self._pad_style

        if subframe_pad:
            pad = '.'.join([padding, subframe_pad])
        else:
            pad = padding
        zfill = self.getPaddingNum(padding, pad_style=pad_style)

        # Set all fields atomically after parsing valid padding characters
        self._frame_pad = padding
        self._pad = pad
        self._zfill = zfill

    def subframePadding(self) -> str:
        """
        Return the padding characters for subframes in the sequence.

        Returns:
            str: sequence padding
        """
        return self._subframe_pad

    def setSubframePadding(self, padding: str):
        """
        Set new padding characters for the subframes in the sequence.
        i.e. "#" or "@@@", or an empty string to disable range
        formatting.

        Args:
            padding (str): sequence padding to set

        Raises:
            ValueError: if unrecognized padding characters are provided
        """
        frame_pad = self._frame_pad
        subframe_pad = padding
        pad_style = self._pad_style

        if subframe_pad:
            pad = '.'.join([frame_pad, subframe_pad])
        else:
            pad = frame_pad
        decimal_places = self.getPaddingNum(subframe_pad, pad_style=pad_style)

        # Set all fields atomically after parsing valid padding characters
        self._subframe_pad = subframe_pad
        self._pad = pad
        self._decimal_places = decimal_places

    def frameSet(self) -> FrameSet | None:
        """
        Return the :class:`.FrameSet` of the sequence if specified,
        otherwise None.

        Returns:
            :class:`.FrameSet` or None:
        """
        return self._frameSet

    def setFrameSet(self, frameSet: FrameSet | None):
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

        if not self._pad:
            self.setPadding(self._DEFAULT_PAD_CHAR)

    def extension(self) -> str:
        """
        Return the file extension of the sequence, including leading period.

        Returns:
            str:
        """
        return self._ext

    def setExtension(self, ext: str):
        """
        Set a new file extension for the sequence.

        Note:
            A leading period will be added if none is provided.

        Args:
            ext (str): the new file extension
        """
        if ext and ext[0] != ".":
            ext = "." + ext
        self._ext = utils.asString(ext)

    def setExtention(self, ext: str):
        """
        Deprecated: use :meth:`setExtension`.

        Args:
            ext (str):
        """
        import warnings
        msg = "the setExtention method is deprecated, please use setExtension"
        warnings.warn(msg)
        self.setExtension(ext)

    def frameRange(self) -> str:
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
        if not self._pad:
            self.setPadding(self._DEFAULT_PAD_CHAR)

    def invertedFrameRange(self) -> str:
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

    def start(self) -> int:
        """
        Returns the start frame of the sequence's :class:`.FrameSet`.
        Will return 0 if the sequence has no frame pattern.

        Returns:
            int:
        """
        if not self._frameSet:
            return 0
        return self._frameSet.start()

    def end(self) -> int:
        """
        Returns the end frame of the sequences :class:`.FrameSet`.
        Will return 0 if the sequence has no frame pattern.

        Returns:
            int:
        """
        if not self._frameSet:
            return 0
        return self._frameSet.end()

    def zfill(self) -> int:
        """
        Returns the zfill depth (ie the number of zeroes to pad with).

        Returns:
            int:
        """
        return self._zfill

    def decimalPlaces(self) -> int:
        """
        Returns the number of decimal places to output.

        Returns:
            int or None:
        """
        return self._decimal_places

    def frame(self, frame: int|float|decimal.Decimal|str) -> str:
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
        zframe: object = None
        if self._zfill == 0:
            # There may have been no placeholder for frame IDs in
            # the sequence, in which case we don't want to insert
            # a frame ID
            zframe = ""
        else:
            if not isinstance(frame, (int, float, decimal.Decimal)):
                try:
                    frame = int(frame)
                except ValueError:
                    try:
                        frame = decimal.Decimal(frame)
                    except decimal.DecimalException:
                        zframe = frame
            if zframe is None:
                zframe = utils.pad(frame, self._zfill, self._decimal_places)

        return str("".join((self._dir, self._base, str(zframe), self._ext)))

    def index(self, idx: int) -> str:
        """
        Return the path to the file at the given index.

        Args:
            idx (int): the desired index

        Returns:
            str:
        """
        return self.__getitem__(idx)

    def batches(self, batch_size: int, paths: bool = False) -> typing.Iterable[str | FileSequence]:
        """
        Returns a generator that yields groups of file paths, up to ``batch_size``.
        Convenience method for ``fileseq.utils.batchIterable(self, batch_size)``
        If ``paths=False``, each batch is a new ``FileSequence`` subrange.
        If ``paths=True``, each batch is an islice generator object of each file
        path in the subrange.

        Args:
            batch_size (int): max file paths in each batch
            paths (bool): if True, generate individual file paths instead of FileSequences

        Returns:
            generator: yields batches of file paths or FileSequence subranges of sequence
        """
        if len(self) == 0:
            return []

        if paths:
            # They just want batches of the individual file paths
            return utils.batchIterable(self, batch_size)

        # generate batches of index ranges for the current sequence
        frame_gen = utils.batchFrames(0, len(self) - 1, batch_size)
        return (self[f.start:f.stop + 1] for f in frame_gen)

    def __setstate__(self, state):
        """
        Allows for de-serialization from a pickled :class:`FileSequence`.

        Args:
            state (dict): Pickle dictionary produced by default pickle implementation
        """
        for name, value in state.items():
            self.__dict__[name] = value
        self.__dict__.setdefault('_pad_style', PAD_STYLE_DEFAULT)
        self.__dict__.setdefault('_frame_pad', self._pad)
        self.__dict__.setdefault('_subframe_pad', '')
        self.__dict__.setdefault('_decimal_places', 0)

    def to_dict(self) -> dict:
        """
        Convert sequence object into a state dict that is suitable for
        further serialization, such as to JSON

        Returns:
            dict: state of the current sequence object
        """
        state = self.__dict__.copy()
        state['_pad_style'] = str(self._pad_style)
        state['_frameSet'] = None
        if self._frameSet is not None:
            state['_frameSet'] = self._frameSet.__getstate__()
        return state

    @classmethod
    def from_dict(cls, state: dict) -> FileSequence:
        """
        Constructor to create a new sequence object from a state
        that was previously returned by :meth:`FileSequence.to_dict`

        Args:
            state (dict): state returned from :meth:`FileSequence.to_dict`

        Returns:
            :obj:`FileSequence`
        """
        state = state.copy()
        frameSet = FrameSet.__new__(FrameSet)
        frameSet.__setstate__(tuple(state['_frameSet']))
        padStyle = constants._PadStyle(state['_pad_style'])
        if padStyle not in REVERSE_PAD_MAP:
            raise ValueError("bad pad style constant value %r" % padStyle)
        state['_pad_style'] = padStyle
        state['_frameSet'] = frameSet
        fs = cls.__new__(cls)
        fs.__setstate__(state)
        return fs

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
            return str(self)

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
        parts = [
            self._dir,
            self._base,
            frameSet,
            self._pad if frameSet else "",
            self._ext,
        ]
        return "".join(parts)

    def __repr__(self):
        try:
            return "<%s: %r>" % (self.__class__.__name__, self.__str__())
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
            cls,
            paths: typing.Iterable[str],
            using: FileSequence|None = None,
            pad_style: constants._PadStyle = PAD_STYLE_DEFAULT,
            allow_subframes: bool = False) -> typing.Iterator[FileSequence]:
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
            pad_style (`PAD_STYLE_DEFAULT` or `PAD_STYLE_HASH1` or `PAD_STYLE_HASH4`): padding style
            allow_subframes (bool): if True, handle subframe filenames

        Yields:
            :obj:`FileSequence`:
        """
        seqs: dict[tuple[str, str, str, int], set[str]] = {}
        if allow_subframes:
            _check = cls.DISK_SUB_RE.match
        else:
            _check = cls.DISK_RE.match

        if isinstance(using, FileSequence):
            dirname, basename, ext = using.dirname(), using.basename(), using.extension()
            head: int = len(dirname + basename)
            tail: int = -len(ext)
            frames: set[str] = set()

            path: str
            for path in filter(None, map(utils.asString, paths)):
                frame = path[head:tail]  # type: ignore
                try:
                    int(frame)
                except ValueError:
                    if not allow_subframes:
                        continue
                    try:
                        decimal.Decimal(frame)
                    except decimal.DecimalException:
                        continue
                _, _, subframe = frame.partition(".")
                key = (dirname, basename, ext, len(subframe))
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

        def start_new_seq():
            seq = cls.__new__(cls)
            seq._dir = dirname or ''
            seq._base = basename or ''
            seq._ext = ext or ''
            return seq

        def finish_new_seq(seq):
            if seq._subframe_pad:
                seq._pad = '.'.join([seq._frame_pad, seq._subframe_pad])
            else:
                seq._pad = seq._frame_pad

            seq.__init__(utils.asString(seq), pad_style=pad_style, allow_subframes=allow_subframes)

        def get_frame_width(frame_str):
            frame_num, _, _ = frame_str.partition(".")
            return len(frame_num)

        def get_frame_minwidth(frame_str):
            # find the smallest padding width for a frame string
            frame_num, _, _ = frame_str.partition(".")
            size = len(frame_num)
            num = int(frame_num)
            num_size = len(str(num))
            if size == num_size:
                return 1
            return size

        def frames_to_seq(frames, pad_length, decimal_places):
            seq = start_new_seq()
            seq._frameSet = FrameSet(sorted(decimal.Decimal(f) for f in frames))
            seq._frame_pad = cls.getPaddingChars(pad_length, pad_style=pad_style)
            if decimal_places:
                seq._subframe_pad = cls.getPaddingChars(decimal_places, pad_style=pad_style)
            else:
                seq._subframe_pad = ''
            finish_new_seq(seq)
            return seq

        for (dirname, basename, ext, decimal_places), frames in seqs.items():
            # Short-circuit logic if we do not have multiple frames, since we
            # only need to build and return a single simple sequence
            if not frames:
                seq = start_new_seq()
                seq._frameSet = None
                seq._frame_pad = ''
                seq._subframe_pad = ''
                finish_new_seq(seq)
                yield seq
                continue

            # If we have multiple frames, then we need to check them for different
            # padding and possibly yield more than one sequence.

            # sort the frame list by their string padding width
            sorted_frames = sorted(((get_frame_width(f), f) for f in frames), key=operator.itemgetter(0))

            current_frames: list[str] = []
            current_width = None

            for width, frame in sorted_frames:
                # initialize on first item
                if current_width is None:
                    current_width = width

                if width != current_width and get_frame_minwidth(frame) > current_width:
                    # We have a new padding length.
                    # Commit the current sequence, and then start a new one.
                    yield frames_to_seq(current_frames, current_width, decimal_places)

                    # Start tracking the next group of frames using the new length
                    current_frames = [frame]
                    current_width = width
                    continue

                current_frames.append(frame)

            # Commit the remaining frames as a sequence
            if current_frames:
                yield frames_to_seq(current_frames, current_width, decimal_places)

    @classmethod
    def findSequencesInList(cls,
                            paths: typing.Iterable[str],
                            pad_style: constants._PadStyle = PAD_STYLE_DEFAULT,
                            allow_subframes: bool = False) -> list[FileSequence]:
        """
        Returns the list of discrete sequences within paths.  This does not try
        to determine if the files actually exist on disk, it assumes you
        already know that.

        Args:
            paths (list[str]): a list of paths
            pad_style (`PAD_STYLE_DEFAULT` or `PAD_STYLE_HASH1` or `PAD_STYLE_HASH4`): padding style
            allow_subframes (bool): if True, handle subframe filenames

        Returns:
            list:
        """
        return list(
            cls.yield_sequences_in_list(paths, pad_style=pad_style, allow_subframes=allow_subframes)
        )

    @classmethod
    def findSequencesOnDisk(
            cls,
            pattern: str,
            include_hidden: bool = False,
            strictPadding: bool = False,
            pad_style: constants._PadStyle = PAD_STYLE_DEFAULT,
            allow_subframes: bool = False) -> list[FileSequence]:
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

        Case-sensitive matching follows POSIX behavior, even on Windows platforms.
        "file.1.png" and "file.2.PNG" result in two different sequences.

        Examples::

            FileSequence.findSequencesOnDisk('/path/to/files/image_stereo_{left,right}.#.jpg')
            FileSequence.findSequencesOnDisk('/path/to/files/imag?_*_{left,right}.@@@.jpg', strictPadding=True)

        Args:
            pattern (str): directory to scan, or pattern to filter in directory
            include_hidden (bool): if true, show .hidden files as well
            strictPadding (bool): if True, ignore files with padding length different from pattern
            pad_style (`PAD_STYLE_DEFAULT` or `PAD_STYLE_HASH1` or `PAD_STYLE_HASH4`): padding style
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
                msg = 'Invalid file pattern: {!r}'.format(filepat)
                raise FileSeqException(msg)

            if seq.padding() and strictPadding:
                get_frame = lambda f: _match_pattern(f).group(1)  # type: ignore
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
        files: typing.Iterable[str] = ret[-1] if ret else []

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
    def findSequenceOnDisk(
            cls,
            pattern: str,
            strictPadding: bool = False,
            pad_style: constants._PadStyle = PAD_STYLE_DEFAULT,
            allow_subframes: bool = False,
            force_case_sensitive: bool = True,
            preserve_padding: bool = False) -> FileSequence:
        """
        Search for a specific sequence on disk.

        The padding characters used in the `pattern` are used to filter the
        frame values of the files on disk (if `strictPadding` is True).

        Case-sensitive matching follows POSIX behavior, even on Windows platforms.
        "file.1.png" and "file.2.PNG" result in two different sequences.
        This behavior can be disabled on Windows by setting `force_case_sensitive=False`.

        By default, the returned sequence will use the "#@" padding character format.
        If ``preserve_padding=True``, then preserve the original `pattern` padding character
        format, as long as the padding length matches the existing sequence. In the case of
        ``strictPadding=False`` and the original padding length not matching the existing
        sequence, then the "#@" format will still be used in the result.

        Examples:
            Find sequence matching basename and extension, and a wildcard for
            any frame.
            returns bar.1.exr bar.10.exr, bar.100.exr, bar.1000.exr, inclusive:

                ``FileSequence.findSequenceOnDisk("seq/bar@@@@.exr")``

            Find exactly 4-padded sequence, i.e. seq/bar1-100#.exr
            returns only frames bar1000.exr through bar9999.exr

                ``FileSequence.findSequenceOnDisk("seq/bar#.exr", strictPadding=True)``

            Find exactly 3-padded sequence, i.e. seq/bar1-3%03d.exr and
            return sequence that preserves the original printf padding format

                ``FileSequence.findSequenceOnDisk("seq/bar%03d.exr", strictPadding=True, preserve_padding=True)``

        Note:
            Unlike `findSequencesOnDisk`, general wildcard characters ("*", "?") are not
            supported and result in undefined behavior. Only the frame component of the paths may
            be replaced with padding characters to serve as a limited wildcard.

        Args:
            pattern (str): the sequence pattern being searched for
            strictPadding (bool): if True, ignore files with padding length different from `pattern`
            pad_style (`PAD_STYLE_DEFAULT` or `PAD_STYLE_HASH1` or `PAD_STYLE_HASH4`): padding style
            allow_subframes (bool): if True, handle subframe filenames
            force_case_sensitive (bool): force posix-style case-sensitive matching on Windows filesystems
            preserve_padding (bool): if True, preserve pattern-provided padding characters in returned
                sequence, if the padding length matches. Default: conform padding to "#@" style.

        Returns:
            FileSequence: A single matching file sequence existing on disk

        Raises:
            :class:`.FileSeqException`: if no sequence is found on disk
        """
        seq = cls(pattern, allow_subframes=allow_subframes, pad_style=pad_style)

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

        if sys.platform == 'win32':
            # apply normpath in either case, as glob on windows could lead to
            # mixed path separators:  path/foo\\bar.ext
            normpath = os.path.normpath
            globbed = (normpath(p) for p in globbed)
            if force_case_sensitive:
                # windows: treat pattern matches as case-sensitive to align
                # with posix behavior
                patt = normpath(patt)
                case_match = re.compile(fnmatch.translate(patt)).match
                globbed = (p for p in globbed if case_match(p))

        pad_filter_ctx = cls._FilterByPaddingNum()

        if pad:
            patt = r'\A'
            if dirname:
                patt = r'.*[/\\]'
            patt += re.escape(basename) + '(.*)' + re.escape(ext) + r'\Z'

            def get_frame(f):
                return re.match(patt, f, re.I).group(1)

            if strictPadding:
                globbed = pad_filter_ctx(
                    globbed,
                    seq.zfill(),
                    decimal_places=seq.decimalPlaces(),
                    get_frame=get_frame
                )
                if not preserve_padding:
                    frame_pad = cls.conformPadding(frame_pad, pad_style=pad_style)
                    subframe_pad = cls.conformPadding(subframe_pad, pad_style=pad_style)
            else:
                globbed = pad_filter_ctx(
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
                if pad:
                    if strictPadding:
                        # The match is already using the same padding width as the
                        # original pattern, so we can just propagate the padding
                        # characters. Depending on whether preserve_padding was set,
                        # the padding characters may or may not have been conformed
                        match.setFramePadding(frame_pad)
                        match.setSubframePadding(subframe_pad)

                    elif preserve_padding:
                        # The match was not guaranteed to have the same padding
                        # width as the original pattern. But if we can check that
                        # they are equal then we can preserve the original padding
                        # characters
                        if seq.zfill() == match.zfill():
                            match.setFramePadding(frame_pad)
                        elif not pad_filter_ctx.has_padded_frames and seq.zfill() <= match.zfill():
                            match.setFramePadding(frame_pad)

                        if seq.decimalPlaces() == match.decimalPlaces():
                            match.setSubframePadding(subframe_pad)
                        elif not pad_filter_ctx.has_padded_subframes and seq.decimalPlaces() <= match.decimalPlaces():
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
    def _globCharsToRegex(filename: str) -> str:
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

    class _FilterByPaddingNum(object):
        def __init__(self):
            # Tracks whether a padded frame has been yielded:
            #       padded: file.0001.ext
            #   not padded: file.1001.ext
            self.has_padded_frames = False
            self.has_padded_subframes = False

        def __call__(self, iterable, zfill, decimal_places=0, get_frame=None):
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
                _check = FileSequence.DISK_RE.match
            else:
                _check = FileSequence.DISK_SUB_RE.match

            self.has_padded_frames = False
            self.has_padded_subframes = False

            has_padded_frame = False
            has_padded_subframe = False

            def check_padded(frame):
                return frame and (frame[0] == '0' or frame[:2] == '-0')

            def set_has_padded():
                if has_padded_frame:
                    self.has_padded_frames = True
                if has_padded_subframe:
                    self.has_padded_subframes = True

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

                has_padded_frame = check_padded(frame)
                has_padded_subframe = check_padded(subframe)

                if zfill is None:
                    set_has_padded()
                    # We have a parsed frame but are not filtering by
                    # a specific zfill
                    yield item
                    continue

                if has_padded_frame:
                    if len(frame) == zfill:
                        set_has_padded()
                        # A frame leading with '0' is explicitly
                        # padded and can only be a match if its exactly
                        # the target padding number
                        yield item
                    continue

                if len(frame) >= zfill:
                    set_has_padded()
                    # A frame that does not lead with '0' can match
                    # a padding width >= to the target padding number
                    yield item
                    continue

    @classmethod
    def _filterByPaddingNum(cls, *args, **kwargs):
        ctx = cls._FilterByPaddingNum()
        return ctx(*args, **kwargs)

    @classmethod
    def getPaddingChars(cls, num: int, pad_style: constants._PadStyle = PAD_STYLE_DEFAULT) -> str:
        """
        Given a particular amount of padding, return the proper padding characters.

        Args:
            num (int): required width of string with padding
            pad_style (`PAD_STYLE_DEFAULT` or `PAD_STYLE_HASH1` or `PAD_STYLE_HASH4`): padding style

        Returns:
            str:
        """
        num = max(1, num)
        reverse_pad_map = cls.REVERSE_PAD_MAP[pad_style]

        # Find the widest padding character that can be used alone
        for width in sorted(reverse_pad_map, reverse=True):
            if num % width == 0:
                return reverse_pad_map[width] * (num // width)

        # Should never reach here as all styles should have an entry for width 1
        raise FileSeqException('REVERSE_PAD_MAP missing pad character for width 1')

    @classmethod
    def getPaddingNum(cls, chars: str, pad_style: constants._PadStyle = PAD_STYLE_DEFAULT) -> int:
        """
        Given a supported group of padding characters, return the amount of padding.

        Args:
            chars (str): a supported group of padding characters
            pad_style (`PAD_STYLE_DEFAULT` or `PAD_STYLE_HASH1` or `PAD_STYLE_HASH4`): padding style

        Returns:
            int:

        Raises:
            ValueError: if unsupported padding character is detected
        """
        if not chars:
            return 0

        if chars in UDIM_PADDING_PATTERNS:
            return 4

        match = PRINTF_SYNTAX_PADDING_RE.match(chars) or HOUDINI_SYNTAX_PADDING_RE.match(chars)
        if match:
            paddingNumStr = match.group(1)
            paddingNum = int(paddingNumStr) if paddingNumStr else 1
            return max(paddingNum, 1)

        char = ''
        rval = 0
        try:
            for char in chars:
                rval += cls.PAD_MAP[char][pad_style]
            return rval
        except KeyError:
            msg = "Detected an unsupported padding character: \"{}\"."
            msg += " Supported padding characters: {}, printf, houdini or UDIM syntax padding"
            msg += " %<int>d"
            raise ValueError(msg.format(char, utils.asString(list(cls.PAD_MAP))))

    @classmethod
    def conformPadding(cls, chars: str, pad_style: constants._PadStyle = PAD_STYLE_DEFAULT) -> str:
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
            pad_style (`PAD_STYLE_DEFAULT` or `PAD_STYLE_HASH1` or `PAD_STYLE_HASH4`): padding style

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
