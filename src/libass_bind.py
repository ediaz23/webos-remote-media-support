import os
import ctypes as C


def find_lib_file(name: str) -> str:
    HERE = os.path.dirname(os.path.abspath(__file__))
    CANDIDATES = [
        os.path.join(HERE, name),
        os.path.join(HERE, '..', 'dist', 'bin', name),
    ]

    lib_path = None
    for p in CANDIDATES:
        p = os.path.abspath(p)
        if os.path.isfile(p):
            lib_path = p
            break
    return lib_path


lib_path = find_lib_file('libwrms_libass.so')
if not lib_path:
    raise RuntimeError('libwrms_libass.so not found (src/ or dist/bin/)')

lib = C.CDLL(lib_path)
