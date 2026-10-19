"""Minimal reader/encoder for IGA version 0x0D archives (Crash Team Racing Nitro-Fueled .pak)."""
import lzma
import struct

CHUNK = 0x8000
LZMA_PROPS = b'\x5d\x00\x80\x00\x00'  # lc=3 lp=0 pb=2, 32 KiB dictionary


class IGA:
    def __init__(self, path, mode='rb'):
        self.f = open(path, mode)
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
        f.seek(self.nt)
        t = f.read(ntsz)
        self.entries = []
        for i in range(self.n):
            off, size, aux, mode_ = struct.unpack_from('<4I', desc, 16 * i)
            no = struct.unpack_from('<I', t, 4 * i)[0]
            name = t[no:t.index(b'\0', no)].decode('latin1')
            self.entries.append(dict(i=i, off=off, size=size, aux=aux, mode=mode_, name=name))

    def true_off(self, e):
        """Entry offsets are 32-bit; archives over 4 GiB wrap, so find the copy that starts a chunk."""
        for k in range(4):
            off = e['off'] + (k << 32)
            self.f.seek(off)
            head = self.f.read(9)
            if len(head) == 9 and head[4:] == LZMA_PROPS:
                return off
        raise ValueError('no LZMA chunk found for ' + e['name'])

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
            out += lzma.LZMADecompressor(lzma.FORMAT_ALONE).decompress(
                props + struct.pack('<q', -1) + comp, max_length=blk)
            pos += 9 + csize
            if len(out) < e['aux']:
                pos = -(-pos // self.align) * self.align
        used = pos - off
        return bytes(out), off, used, -(-used // self.align) * self.align

    @staticmethod
    def encode(data):
        """Compress into the chunk stream the game reads (u32 size, props, LZMA data)."""
        out = bytearray()
        for i in range(0, len(data), CHUNK):
            c = lzma.LZMACompressor(lzma.FORMAT_RAW, filters=[
                {'id': lzma.FILTER_LZMA1, 'lc': 3, 'lp': 0, 'pb': 2, 'dict_size': CHUNK,
                 'preset': 9 | lzma.PRESET_EXTREME}])
            comp = c.compress(data[i:i + CHUNK]) + c.flush()
            out += struct.pack('<I', len(comp)) + LZMA_PROPS + comp
        return bytes(out)
