"""
fileseq - A simple python library for parsing file sequence strings commonly
used in VFX and animation applications.
"""

import os
import re

__all__ = [ "FrameSet",
            "FileSequence",
            "framesToFrameRange",
            "findSequencesOnDisk",
            "findSequenceOnDisk",
            "getPaddingChars",
            "ParseException" ]

_PADDING = {"#": 4, "@": 1}

_PATTERNS = [
    re.compile("^(\-?[0-9]+)\-(\-?[0-9]+)$"),
    re.compile("^(\-?[0-9]+)$"),
    re.compile("^(\-?[0-9]+)\-(\-?[0-9]+)([:xy]{1})([0-9]+)$")
]

_SEQ_PATTERN = re.compile("^(.*/)?(?:$|(.+?)([\:xy\-0-9,]*)([\#\@]*)(?:(\.[^.]*$)|$))")

_ON_DISK_PATTERN = re.compile("^(.*/)?(?:$|(.+?)([\-0-9]{1,})(?:(\.[^.]*$)|$))")


class ParseException(Exception):
    """Thrown after a frame range or file sequence parse error."""

class FrameSet(object):
    """
    A FrameSet represents an ordered and unique set of frames in a frame range.  A frame range
    can be expressed in the following ways:
        
        1-5
        1-5,10-20
        1-100x5 (every fifth frame)
        1-100y5 (opposite of above, fills in missing frames)
        1-100:4 (same as 1-100x4,1-100x3,1-100x2,1-100)
    """
    
    @staticmethod
    def isFrameRange(frange):
        """
        Return true of the given string is a frame range.  Any padding
        characters, such as '#' and '@' are ignored.
        """
        frange = str(frange)
        frange = frange.replace("#", "").replace("@", "")
        if not frange:
            return False
        for part in frange.split(","):
            matched = False
            for p in _PATTERNS:
                if p.match(part):
                    matched = True
                    break
            if not matched:
                return False
        return True
    
    def __init__(self, frange):
        
        self.__frange = frange
        self.__set = set()
        self.__list = list()
        
        for part in frange.split(","):
            matched = False
            for pat in _PATTERNS:
                match = pat.match(part)
                if match:
                    matched = True
                    self.__handleMatch(match)
                    break
            if not matched:
                raise ParseException("Failed to parse frame range: %s on part '%s'" % (frange, part))
    
    def index(self, frame):
        """
        Return the index of the given frame number
        """
        return self.__list.index(frame)

    def frame(self, idx):
        """
        Return the frame at the given index.
        """
        return self.__list[idx]
    
    def hasFrame(self, frame):
        """
        Return true if the FrameSet contains the supplied frame number.
        """
        return frame in self.__set

    def start(self):
        return self.__list[0]

    def end(self):
        return self.__list[-1]

    def frameRange(self):
        return self.__frange
    
    def normalize(self):
        """
        Normalizes the current FramSet and returns a new sorted and
        compacted FrameSet
        """
        return FrameSet(framesToFrameRange(self.__list))
    
    def __handleMatch(self, match):
        """
        Handle the different types of sequence pattern matches.
        """
        groups = match.groups()
        length = len(groups)
        if length == 2:
            self.__addFrames(xrange(int(groups[0]), int(groups[1])+1))
        elif length == 1:
            self.__addFrames([int(groups[0])])
        elif length == 4:
            chunk = int(groups[3])
            if chunk == 0:
                ParseException("Failed to parse part of range: %s , invalid use of the number zero.")
            
            start = int(groups[0])
            end = int(groups[1])
            modifier = groups[2]
            
            if modifier == "x":
                self.__addFrames(xrange(start, end+1, chunk))
            elif modifier == ":":
                for stagger in xrange(chunk, 0, -1):
                    self.__addFrames(xrange(start, end+1, stagger))
            elif modifier == "y":
                not_good = frozenset(xrange(start, end+1, chunk))
                self.__addFrames([f for f in xrange(start, end+1)
                    if f not in not_good])
    
    def __addFrames(self, frames):
        """
        Filters the given set of frames to a unique list and adds them to the
        underlying frame list.
        """
        _f = [f for f in frames if f not in self.__set]
        if not _f:
            return
        self.__set.update(_f)
        self.__list+=_f
    
    def __getitem__(self, index):
        return self.__list[index]
    
    def __len__(self):
        return len(self.__list)
    
    def __str__(self):
        return self.__frange
    
    def __iter__(self):
        for i in self.__list:
            yield i

class FileSequence(object):
    """
    FileSequence represents an ordered sequence of files.
    """
    def __init__(self, sequence):
        m = _SEQ_PATTERN.match(sequence)
        if not m:
            raise ParseException("Failed to parse FileSequence: %s" % sequence)
        self.__dir = m.group(1)
        if not self.__dir:
            self.__dir = ""
        self.__basename = m.group(2)
        self.__padding = m.group(4)
        if m.group(3):
            self.__frameSet = FrameSet(m.group(3))
        else:
            self.__frameSet = None
        self.__ext = m.group(5)
        self.__zfill = sum([_PADDING[c] for c in self.__padding])
    
    def dirname(self):
        """
        Return the directory name of the sequence.
        """
        return self.__dir
    
    def basename(self):
        """
        Return the basenae of the sequence.
        """
        return self.__basename
    
    def padding(self):
        """
        Return the the padding characters in the sequence.
        """
        return self.__padding

    def start(self):
        return self.__frameSet.start()


    def end(self):
        return self.__frameSet.end()

    def frameRange(self):
        return self.__frameSet.frameRange()
    
    def frameSet(self):
        """
        Return the FrameSet of the sequence if one was specified, otherwise return None
        """
        return self.__frameSet
    
    def extension(self):
        """
        Return the file extension in the sequence. This includes the leading period.
        """
        return self.__ext
    
    def frame(self, frame):
        """
        Return a path go the given frame in the sequence.  Integer or string digits
        are treated as a frame number and padding is applied, all other values 
        are passed though. Example:

        seq.frame(1)
        >> /foo/bar.0001.exr

        seq.frame("#")
        >> /foo/bar.#.exr 
        """
        try:
            _fr = int(frame)
            zframe = str(frame).zfill(self.__zfill)
        except ValueError:
            zframe = frame

        return "".join((
                self.__dir,
                self.__basename,
                zframe,
                self.__ext))

    def index(self, idx):
        """
        Return the path to the file at the given index.
        """
        return self.frame(self.__frameSet[idx])

    def setDirname(self, dirname):
        """
        Set a new dirname for the sequence.
        """
        self.__dir = dirname
    
    def setBasename(self, base):
        """
        Set a new basename for the sequence.
        """
        self.__basename = base
    
    def setPadding(self, padding):
        """
        Set new padding for the sequence.
        """
        self.__padding = padding
        self.__zfill = sum([_PADDING[c] for c in self.__padding])
    
    def setExtention(self, ext):
        """
        Set a new file extension for the sequence.
        """
        if ext[0] != ".":
            ext = "." + ext
        self.__ext = ext

    def setFrameSet(self, frameSet):
        """
        Set a new FrameSet for the sequence.
        """
        self.__frameSet = frameSet
    
    def setFrameRange(self, frange):
        """
        Set a new frame range for the sequence.
        """
        self.__frameSet = FrameSet(frange)
    
    def __iter__(self):
        for f in self.__frameSet:
            yield self.frame(f)
    
    def __getitem__(self, idx):
        return self.index(idx)
    
    def __len__(self):
        return len(self.__frameSet)
    
    def __str__(self):
        return "".join((
            self.__dir,
            self.__basename,
            str(self.__frameSet or ""),
            self.__padding,
            self.__ext))

def framesToFrameRange(frames, sort=True):
    """
    Return a string frame range represenation of the
    given list of frame numbers.
    
    Example:
        framesToFrameRange([1,2,3,4,5])
        >> "1-5"
    """
    if len(frames) == 1:
        return str(frames[0])
    
    if sort:
        frames.sort()
    
    result = []
    def append(start, end, chunk, count):
        if end - start == chunk:
            result.append("%d,%d" % (start, end))
        elif count == 0:
            result.append("%d" % start)
        elif chunk <= 1:
            result.append("%d-%d" % (start, end))
        else:
            result.append("%d-%dx%d" % (start, end, chunk))

    start = frames[0]
    chunk = frames[1] - frames[0]
    count = 0

    for num, frame in enumerate(frames):
        if num > 0:
            diff = frames[num] - frames[num-1]
            # We've encountered the same frame so just
            # skip over it.
            if diff == 0:
                chunk = 1
                continue

            if diff != chunk:
                append(start, frames[num-1], chunk, count)
                # Look forward for our new chunk
                try:
                    chunk = frames[num+1] - frames[num]
                except IndexError:
                    chunk = 1
                count = 0
                start = frames[num]
            else:
                count+=1

    append(start, frame, chunk, count)
    return ",".join(result)

def findSequencesOnDisk(path):
    """
    Return a list of sequences found in the given directory.
    """
    result = []
    seqs = { }

    for _file in os.listdir(path):

        if not os.path.isfile(os.path.join(path, _file)):
            continue

        m = _ON_DISK_PATTERN.match(os.path.join(path, _file))
        if not m:
            continue
        
        # Key is made up of of dir, base, and ext
        key = (m.group(1), m.group(2), m.group(4))
        frames = seqs.get(key)
        if not frames:
            frames = [[], len(m.group(3))]
            seqs[key] = frames
        frames[0].append(int(m.group(3)))
    
    for key, frames in seqs.iteritems():
        frame_range = framesToFrameRange(frames[0])
        try:
            seq = "".join((
                key[0], key[1], frame_range, getPaddingChars(frames[1]), key[2]))
        except TypeError:
            continue        
        result.append(FileSequence(seq))

    return result

def findSequenceOnDisk(path):
    """
    Searches for a specific sequence on disk, for example,
    findSequenceOnDisk("seq/bar#.exr") (or any other pattern supported by fileseq)
    """
    for seq in findSequencesOnDisk(os.path.dirname(path)):
        if seq.basename() == FileSequence(path).basename():
            return seq
    raise ValueError("No sequence found on disk matching %s"%path)

def getPaddingChars(num):
    """
    Given a particular amount of padding, return the propper padding characters.
    """
    if num == 0:
        return "@"
    if num % 4 == 0:
        return "#" * (num / 4)
    else:
        return "@" * num
