
from ctypes import c_int, c_uint32, c_size_t, c_uint8, c_void_p, pointer, cast
from ctypes import Structure, POINTER
from io import BytesIO
from PIL import Image


# structs for wrms_render_a8 / wrms_free_frame
class WrmsSprite(Structure):
    _fields_ = [
        ('x', c_int),
        ('y', c_int),
        ('w', c_int),
        ('h', c_int),
        ('stride', c_int),
        ('color', c_uint32),
        ('offset', c_uint32),
    ]


class WrmsFrame(Structure):
    _fields_ = [
        ('sprites', POINTER(WrmsSprite)),
        ('sprites_len', c_size_t),
        ('bitmaps', POINTER(c_uint8)),
        ('bitmaps_len', c_size_t),
    ]


def _rgba_from_libass_color(color: int):
    # libass: (R<<24)|(G<<16)|(B<<8)|Ainv, where A = 255 - Ainv
    r = (color >> 24) & 0xFF
    g = (color >> 16) & 0xFF
    b = (color >> 8) & 0xFF
    a = 255 - (color & 0xFF)
    return r, g, b, a


def render_frame_to_webp(lib, hnd, width: int, height: int, t_ms: int):
    '''
    Calls wrms_render_a8() and composites A8 sprites into an RGBA canvas,
    then returns WebP bytes. Returns None if there are no subtitle images.
    Assumes ctypes signatures for wrms_render_a8/wrms_free_frame are already set.
    '''
    frame = WrmsFrame()
    rc = lib.wrms_render_a8(c_void_p(hnd), int(t_ms), pointer(frame))

    try:
        if rc != 0:
            return None
        if not frame.sprites or frame.sprites_len == 0 or not frame.bitmaps or frame.bitmaps_len == 0:
            return None

        out = bytearray(width * height * 4)  # RGBA, transparent

        bm_addr = cast(frame.bitmaps, c_void_p).value
        bm = (c_uint8 * frame.bitmaps_len).from_address(bm_addr)
        bm_mv = memoryview(bm)

        for i in range(int(frame.sprites_len)):
            sp = frame.sprites[i]

            x0 = int(sp.x)
            y0 = int(sp.y)
            w = int(sp.w)
            h = int(sp.h)
            stride = int(sp.stride)
            off = int(sp.offset)

            r, g, b, a0 = _rgba_from_libass_color(int(sp.color))
            if a0 == 0 or w <= 0 or h <= 0 or stride <= 0:
                continue

            sprite = bm_mv[off: off + stride * h]

            # clip
            sx0 = 0
            sy0 = 0
            dx0 = x0
            dy0 = y0
            if dx0 < 0:
                sx0 = -dx0
                dx0 = 0
            if dy0 < 0:
                sy0 = -dy0
                dy0 = 0

            dw = w - sx0
            dh = h - sy0
            if dx0 + dw > width:
                dw = width - dx0
            if dy0 + dh > height:
                dh = height - dy0
            if dw <= 0 or dh <= 0:
                continue

            # source-over (straight alpha); effective alpha = a0 * mask
            for yy in range(dh):
                src_row = (sy0 + yy) * stride + sx0
                dst_row = (dy0 + yy) * width * 4 + dx0 * 4
                for xx in range(dw):
                    m = sprite[src_row + xx]
                    if m == 0:
                        continue

                    a = (a0 * m + 127) // 255
                    inv = 255 - a

                    di = dst_row + xx * 4
                    dr = out[di + 0]
                    dg = out[di + 1]
                    db = out[di + 2]
                    da = out[di + 3]

                    out[di + 0] = (r * a + dr * inv + 127) // 255
                    out[di + 1] = (g * a + dg * inv + 127) // 255
                    out[di + 2] = (b * a + db * inv + 127) // 255
                    out[di + 3] = a + (da * inv + 127) // 255

        img = Image.frombytes('RGBA', (width, height), bytes(out))
        bio = BytesIO()
        img.save(bio, format='WEBP', lossless=True, method=6)
        return bio.getvalue()

    finally:
        lib.wrms_free_frame(pointer(frame))
