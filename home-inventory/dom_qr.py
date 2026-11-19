"""Minimal QR code encoder (byte mode, versions 1-40), standard library only.

A port of the reference algorithm by Project Nayuki (MIT). Used by dom.py for container and card labels.
encode("tekst") -> list of rows of bools (True = dark module), without the quiet zone.
"""
from __future__ import annotations

ECC_CODEWORDS_PER_BLOCK = {
    "L": (-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28,
          30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    "M": (-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28,
          28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),
    "Q": (-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30, 28, 30, 30, 30, 30, 28,
          30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    "H": (-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28, 30, 24, 30, 30, 30, 30,
          30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
}
NUM_ERROR_CORRECTION_BLOCKS = {
    "L": (-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17,
          18, 19, 19, 20, 21, 22, 24, 25),
    "M": (-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29,
          31, 33, 35, 37, 38, 40, 43, 45, 47, 49),
    "Q": (-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38,
          40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68),
    "H": (-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42, 45,
          48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81),
}
ECL_BITS = {"L": 1, "M": 0, "Q": 3, "H": 2}


def _raw_modules(ver: int) -> int:
    result = (16 * ver + 128) * ver + 64
    if ver >= 2:
        n = ver // 7 + 2
        result -= (25 * n - 10) * n - 55
        if ver >= 7:
            result -= 36
    return result


def _data_codewords(ver: int, ecl: str) -> int:
    return _raw_modules(ver) // 8 - ECC_CODEWORDS_PER_BLOCK[ecl][ver] * NUM_ERROR_CORRECTION_BLOCKS[ecl][ver]


def _gf_mul(x: int, y: int) -> int:
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_mul(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_mul(root, 0x02)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_mul(coef, factor)
    return result


def _alignment_positions(ver: int) -> list[int]:
    if ver == 1:
        return []
    num = ver // 7 + 2
    step = (ver * 8 + num * 3 + 5) // (num * 4 - 4) * 2
    result = [ver * 4 + 10 - i * step for i in range(num - 1)] + [6]
    return list(reversed(result))


class _Grid:
    def __init__(self, ver: int):
        self.size = ver * 4 + 17
        self.m = [[False] * self.size for _ in range(self.size)]
        self.fn = [[False] * self.size for _ in range(self.size)]

    def set_fn(self, x: int, y: int, dark: bool) -> None:
        self.m[y][x] = dark
        self.fn[y][x] = True


def _draw_function_patterns(g: _Grid, ver: int, ecl: str) -> None:
    n = g.size
    for i in range(n):
        g.set_fn(6, i, i % 2 == 0)
        g.set_fn(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < n and 0 <= y < n:
                    g.set_fn(x, y, max(abs(dx), abs(dy)) not in (2, 4))
    pos = _alignment_positions(ver)
    last = len(pos) - 1
    for i, a in enumerate(pos):
        for j, b in enumerate(pos):
            if (i == 0 and j == 0) or (i == 0 and j == last) or (i == last and j == 0):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    g.set_fn(a + dx, b + dy, max(abs(dx), abs(dy)) != 1)
    _draw_format(g, ecl, 0)
    if ver >= 7:
        rem = ver
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = ver << 12 | rem
        for i in range(18):
            bit = (bits >> i) & 1 == 1
            a, b = n - 11 + i % 3, i // 3
            g.set_fn(a, b, bit)
            g.set_fn(b, a, bit)


def _draw_format(g: _Grid, ecl: str, mask: int) -> None:
    data = ECL_BITS[ecl] << 3 | mask
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    bits = (data << 10 | rem) ^ 0x5412
    n = g.size
    for i in range(6):
        g.set_fn(8, i, (bits >> i) & 1 == 1)
    g.set_fn(8, 7, (bits >> 6) & 1 == 1)
    g.set_fn(8, 8, (bits >> 7) & 1 == 1)
    g.set_fn(7, 8, (bits >> 8) & 1 == 1)
    for i in range(9, 15):
        g.set_fn(14 - i, 8, (bits >> i) & 1 == 1)
    for i in range(8):
        g.set_fn(n - 1 - i, 8, (bits >> i) & 1 == 1)
    for i in range(8, 15):
        g.set_fn(8, n - 15 + i, (bits >> i) & 1 == 1)
    g.set_fn(8, n - 8, True)


def _codewords(data: bytes, ver: int, ecl: str) -> list[int]:
    bits: list[int] = []

    def put(val: int, length: int) -> None:
        bits.extend((val >> i) & 1 for i in reversed(range(length)))

    put(0b0100, 4)
    put(len(data), 8 if ver <= 9 else 16)
    for b in data:
        put(b, 8)
    cap = _data_codewords(ver, ecl) * 8
    put(0, min(4, cap - len(bits)))
    put(0, (-len(bits)) % 8)
    pad = 0xEC
    while len(bits) < cap:
        put(pad, 8)
        pad ^= 0xEC ^ 0x11
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]

    nblocks = NUM_ERROR_CORRECTION_BLOCKS[ecl][ver]
    ecc_len = ECC_CODEWORDS_PER_BLOCK[ecl][ver]
    raw = _raw_modules(ver) // 8
    short_blocks = nblocks - raw % nblocks
    short_len = raw // nblocks
    div = _rs_divisor(ecc_len)
    blocks, k = [], 0
    for i in range(nblocks):
        dlen = short_len - ecc_len + (0 if i < short_blocks else 1)
        dat = words[k:k + dlen]
        k += dlen
        ecc = _rs_remainder(dat, div)
        if i < short_blocks:
            dat = dat + [None]
        blocks.append(dat + ecc)
    out = []
    for i in range(len(blocks[0])):
        for j, blk in enumerate(blocks):
            if i != short_len - ecc_len or j >= short_blocks:
                out.append(blk[i])
    return out


def _draw_codewords(g: _Grid, words: list[int]) -> None:
    n = g.size
    i = 0
    right = n - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(n):
            for j in range(2):
                x = right - j
                upward = (right + 1) & 2 == 0
                y = n - 1 - vert if upward else vert
                if not g.fn[y][x] and i < len(words) * 8:
                    g.m[y][x] = (words[i >> 3] >> (7 - (i & 7))) & 1 == 1
                    i += 1
        right -= 2


MASKS = (
    lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0, lambda x, y: (x + y) % 3 == 0,
    lambda x, y: (x // 3 + y // 2) % 2 == 0, lambda x, y: x * y % 2 + x * y % 3 == 0,
    lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0, lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
)


def _apply_mask(g: _Grid, mask: int) -> None:
    f = MASKS[mask]
    for y in range(g.size):
        for x in range(g.size):
            if not g.fn[y][x] and f(x, y):
                g.m[y][x] = not g.m[y][x]


def _penalty(m: list[list[bool]]) -> int:
    n = len(m)
    score = 0
    lines = m + [list(col) for col in zip(*m)]
    for line in lines:
        run, prev = 0, None
        for v in line:
            if v == prev:
                run += 1
            else:
                if run >= 5:
                    score += run - 2
                run, prev = 1, v
        if run >= 5:
            score += run - 2
        s = "".join("1" if v else "0" for v in line)
        for pat in ("10111010000", "00001011101"):
            start = s.find(pat)
            while start != -1:
                score += 40
                start = s.find(pat, start + 1)
    for y in range(n - 1):
        for x in range(n - 1):
            c = m[y][x]
            if c == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                score += 3
    dark = sum(v for row in m for v in row)
    total = n * n
    k = (abs(dark * 20 - total * 10) + total - 1) // total - 1
    return score + k * 10


def encode(text: str | bytes, ecl: str = "M") -> list[list[bool]]:
    data = text.encode("utf-8") if isinstance(text, str) else text
    for ver in range(1, 41):
        if 4 + (8 if ver <= 9 else 16) + 8 * len(data) <= _data_codewords(ver, ecl) * 8:
            break
    else:
        raise ValueError("tekst za długi na kod QR")
    words = _codewords(data, ver, ecl)
    best, best_score = None, None
    for mask in range(8):
        g = _Grid(ver)
        _draw_function_patterns(g, ver, ecl)
        _draw_codewords(g, words)
        _apply_mask(g, mask)
        _draw_format(g, ecl, mask)
        sc = _penalty(g.m)
        if best_score is None or sc < best_score:
            best, best_score = g.m, sc
    return best


def svg_path(matrix: list[list[bool]], x0: float, y0: float, cell: float) -> str:
    """Dark modules as one SVG path, quiet zone not included."""
    parts = []
    for y, row in enumerate(matrix):
        for x, v in enumerate(row):
            if v:
                parts.append(f"M{x0 + x * cell:.3f},{y0 + y * cell:.3f}h{cell:.3f}v{cell:.3f}h{-cell:.3f}z")
    return f'<path d="{"".join(parts)}" fill="#000"/>'
