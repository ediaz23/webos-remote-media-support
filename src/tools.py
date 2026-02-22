
from fontTools.ttLib import TTFont, TTCollection

from ctypes import c_uint8


def load_default_font(lib, hnd, font_path, default_name):
    with open(font_path, 'rb') as f:
        data = f.read()
    arr = (c_uint8 * len(data)).from_buffer_copy(data)
    font_name = get_font_family(font_path) or default_name
    rc = lib.wrms_add_font_mem(hnd, font_name.encode('utf-8'), arr, len(data))
    if rc != 0:
        raise RuntimeError('wrms_add_font_mem rc=%s' % rc)
    return font_name


def get_font_family(path: str):
    result = None
    try:
        if path.lower().endswith(".ttc"):
            tc = TTCollection(path)
            tt = tc.fonts[0] if tc.fonts else None
        else:
            tt = TTFont(path)

        if tt and "name" in tt:
            names = tt["name"].names
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
