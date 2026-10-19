"""Minimal reader/encoder for IGA version 0x0D archives (Crash Team Racing Nitro-Fueled .pak)."""
import lzma
import os
import struct

CHUNK = 0x8000
LZMA_PROPS = b'\x5d\x00\x80\x00\x00'  # lc=3 lp=0 pb=2, 32 KiB dictionary


class IGA:
    def __init__(self, path, mode='rb', base=0, length=None):
        self.base = base
        self.length = os.path.getsize(path) - base if length is None else length
        self.f = ArchiveView(open(path, mode), base, self.length)
        f = self.f
        h = f.read(0x38)
        if h[:4] != b'IGA\x1a' or struct.unpack_from('<I', h, 4)[0] != 0xd:
            raise ValueError('%s is not an IGA v13 archive' % path)
        self.n = struct.unpack_from('<I', h, 0xc)[0]
        self.align = struct.unpack_from('<I', h, 0x10)[0]
        self.nt = struct.unpack_from('<Q', h, 0x28)[0]
        ntsz = struct.unpack_from('<I', h, 0x30)[0]
        f.seek(0x38 + 4 * self.n)
        desc = f.read(16 * self.n)
        if self.nt + ntsz > self.length:
            raise ValueError('archive name table outside container')
        f.seek(self.nt)
        t = f.read(ntsz)
        self.entries = []
        for i in range(self.n):
            off, size, aux, mode_ = struct.unpack_from('<4I', desc, 16 * i)
            no = struct.unpack_from('<I', t, 4 * i)[0]
            name = t[no:t.index(b'\0', no)].decode('latin1')
            self.entries.append(dict(i=i, off=off, size=size, aux=aux, mode=mode_, name=name))

    def true_off(self, e):
        """Decode the 40-bit offset; the low byte of the packed ordinal holds bits 32..39.

        The historical entry key 'size' is this packed ordinal, not a byte length.
        Searching for LZMA headers at wrapped offsets can select an unrelated file.
        """
        off = e['off'] + ((e['size'] & 0xff) << 32)
        self.f.seek(off)
        head = self.f.read(9)
        if len(head) != 9 or head[4:] != LZMA_PROPS:
            raise ValueError('no LZMA chunk at descriptor offset for ' + e['name'])
        return off

    def read(self, e):
        """Return (decompressed bytes, offset, bytes occupied on disk, that rounded up to alignment)."""
        assert e['mode'] >> 24 == 0x20, hex(e['mode'])
        off = pos = self.true_off(e)
        out = bytearray()
        while len(out) < e['aux']:
            self.f.seek(pos)
            csize = struct.unpack('<I', self.f.read(4))[0]
            props = self.f.read(5)
            if props != LZMA_PROPS:
                raise ValueError('unsupported chunk in ' + e['name'])
            blk = min(CHUNK, e['aux'] - len(out))
            comp = self.f.read(csize)
            decoded = lzma.LZMADecompressor(lzma.FORMAT_ALONE).decompress(
                props + struct.pack('<q', -1) + comp, max_length=blk)
            if len(decoded) != blk:
                raise ValueError('short decoded chunk in ' + e['name'])
            out += decoded
            pos += 9 + csize
            if len(out) < e['aux']:
                pos = -(-pos // self.align) * self.align
        used = pos - off
        return bytes(out), off, used, -(-used // self.align) * self.align

    @staticmethod
    def encode(data, align=2048):
        """Compress into the chunk stream the game reads (u32 size, props, LZMA data)."""
        out = bytearray()
        for i in range(0, len(data), CHUNK):
            if out:
                out += bytes(-len(out) % align)
            c = lzma.LZMACompressor(lzma.FORMAT_RAW, filters=[
                {'id': lzma.FILTER_LZMA1, 'lc': 3, 'lp': 0, 'pb': 2, 'dict_size': CHUNK,
                 'preset': 9 | lzma.PRESET_EXTREME}])
            comp = c.compress(data[i:i + CHUNK]) + c.flush()
            out += struct.pack('<I', len(comp)) + LZMA_PROPS + comp
        return bytes(out)


class ArchiveView:
    """Bounded relative access to a raw IGA embedded in a larger archive."""
    def __init__(self, f, base, length):
        self.raw, self.base, self.length, self.pos = f, base, length, 0
        self.raw.seek(base)

    def seek(self, offset):
        if not 0 <= offset <= self.length:
            raise ValueError('seek outside archive container')
        self.pos = offset
        return self.raw.seek(self.base + offset)

    def read(self, size):
        size = min(size, self.length - self.pos)
        data = self.raw.read(size)
        self.pos += len(data)
        return data

    def write(self, data):
        if self.pos + len(data) > self.length:
            raise ValueError('write outside archive container')
        count = self.raw.write(data)
        self.pos += count
        return count

    def flush(self):
        return self.raw.flush()

    def fileno(self):
        return self.raw.fileno()

    def close(self):
        return self.raw.close()
