"""Minimal 8-bit PNG reader/writer. Stdlib only (zlib, struct).

Supports the subset needed for flat-color floor plans: 8-bit depth,
non-interlaced, color types 0 (grayscale), 2 (RGB), 6 (RGBA). Anything
else raises ValueError with a clear message — an honest boundary, not
a silent wrong answer.
"""
import struct
import zlib

_SIG = b"\x89PNG\r\n\x1a\n"


def write_png(path, width, height, rows):
    """Write an 8-bit RGB PNG. rows: height rows of width (r, g, b) tuples."""
    if len(rows) != height:
        raise ValueError("row count mismatch")
    raw = bytearray()
    for row in rows:
        if len(row) != width:
            raise ValueError("row width mismatch")
        raw.append(0)  # filter: none
        for px in row:
            raw.extend(px)

    def chunk(tag, data):
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(_SIG)
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        f.write(chunk(b"IEND", b""))


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read_png(path):
    """Read a PNG -> (width, height, rows of (r, g, b) tuples)."""
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(_SIG):
        raise ValueError("%s: not a PNG" % path)

    pos, idat, meta = 8, bytearray(), None
    while pos + 8 <= len(data):
        (ln,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if tag == b"IHDR":
            meta = struct.unpack(">IIBBBBB", payload)
        elif tag == b"IDAT":
            idat.extend(payload)
        elif tag == b"IEND":
            break
    if meta is None:
        raise ValueError("%s: missing IHDR" % path)

    w, h, depth, ctype, _comp, _filt, inter = meta
    if depth != 8 or inter != 0:
        raise ValueError("%s: need 8-bit non-interlaced PNG" % path)
    if ctype not in (0, 2, 6):
        raise ValueError("%s: unsupported color type %d" % (path, ctype))
    nch = {0: 1, 2: 3, 6: 4}[ctype]

    stride = w * nch
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as e:
        raise ValueError("%s: corrupt IDAT (%s)" % (path, e))

    rows, prev, p = [], bytearray(stride), 0
    for _y in range(h):
        ftype = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        if len(line) != stride:
            raise ValueError("%s: truncated image data" % path)
        p += stride
        for x in range(stride):
            if ftype == 0:
                continue
            a = line[x - nch] if x >= nch else 0
            b = prev[x]
            c = prev[x - nch] if x >= nch else 0
            if ftype == 1:
                line[x] = (line[x] + a) & 255
            elif ftype == 2:
                line[x] = (line[x] + b) & 255
            elif ftype == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif ftype == 4:
                line[x] = (line[x] + _paeth(a, b, c)) & 255
            else:
                raise ValueError("%s: bad filter type %d" % (path, ftype))
        prev = line
        row = []
        for x in range(w):
            i = x * nch
            if ctype == 0:
                row.append((line[i], line[i], line[i]))
            else:  # RGB or RGBA (alpha dropped)
                row.append((line[i], line[i + 1], line[i + 2]))
        rows.append(row)
    return w, h, rows
