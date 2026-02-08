import os
import ctypes as C

HERE = os.path.dirname(os.path.abspath(__file__))

CANDIDATES = [
    os.path.join(HERE, 'libwrms_libass.so'),
    os.path.join(HERE, '..', 'dist', 'bin', 'libwrms_libass.so'),
]

lib_path = None
for p in CANDIDATES:
    p = os.path.abspath(p)
    if os.path.isfile(p):
        lib_path = p
        break

if not lib_path:
    raise RuntimeError('libwrms_libass.so not found (src/ or dist/bin/)')

lib = C.CDLL(lib_path)
