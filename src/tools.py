
import pysubs2
import io
import re
import struct
from fontTools.ttLib import TTFont, TTCollection
from ctypes import c_uint8


def _get_font_family(path: str):
    result = None
    try:
        if path.lower().endswith('.ttc'):
            tc = TTCollection(path)
            tt = tc.fonts[0] if tc.fonts else None
        else:
            tt = TTFont(path)

        if tt and 'name' in tt:
            names = tt['name'].names
            for name_id in (16, 1):  # Preferred Family, Family
                if result is None:
                    for rec in names:
                        if rec.nameID == name_id:
                            try:
                                s = rec.toUnicode()
                            except Exception:
                                s = None
                            if s:
                                s = s.strip()
                                if s:
                                    result = s
                                    break
    except Exception:
        result = None

    return result


def load_default_font(lib, hnd, font_path, default_name):
    with open(font_path, 'rb') as f:
        data = f.read()
    arr = (c_uint8 * len(data)).from_buffer_copy(data)
    font_name = _get_font_family(font_path) or default_name
    rc = lib.wrms_add_font_mem(hnd, font_name.encode('utf-8'), arr, len(data))
    if rc != 0:
        raise RuntimeError('wrms_add_font_mem rc=%s' % rc)
    return font_name


_DYNAMIC_RE = re.compile(
    r'\\move\b|\\t\(|\\k[fo]?\d+|\\fad\b|\\fade\b',
    re.IGNORECASE,
)


def parse_ass_events(ass_text: str) -> list:
    subs = (
        pysubs2.SSAFile.from_string(ass_text)
        if hasattr(pysubs2.SSAFile, 'from_string')
        else pysubs2.load(io.StringIO(ass_text))
    )

    out = []
    for i, ev in enumerate(subs.events):
        start_ms = int(ev.start)
        end_ms = int(ev.end)
        out.append({
            'id': i,
            'start_ms': start_ms,
            'end_ms': end_ms,
            'dur_ms': max(0, end_ms - start_ms),
            'type': 'dynamic' if _DYNAMIC_RE.search(ev.text or '') else 'static',
        })

    return list(sorted(out, key=lambda ev: ev['start_ms']))


def encode_subs(sub_list: list) -> bytearray:
    out = bytearray()
    out += b'WRMS'
    out += struct.pack('<B', 1)
    out += struct.pack('<H', len(sub_list))

    for ev in sub_list:
        if ev['data'] is None:
            out += struct.pack('<iI', ev['id'], 0)
        else:
            out += struct.pack('<iI', ev['id'], len(ev['data']))
            out += ev['data']
    return out
