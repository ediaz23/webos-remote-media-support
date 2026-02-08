
import socket
import threading
import json
import uvicorn
from ctypes import c_void_p, c_int, c_size_t, c_char_p
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from . import libass_bind

lib = libass_bind.lib
APP_PORT = 19090
DISCOVERY_PORT = 19091

c_engine = None


def c_ensure_engine():
    global c_engine
    if c_engine is not None:
        return c_engine

    lib.wrms_create.argtypes = []
    lib.wrms_create.restype = c_void_p

    lib.wrms_destroy.argtypes = [c_void_p]
    lib.wrms_destroy.restype = None

    lib.wrms_set_frame_size.argtypes = [c_void_p, c_int, c_int]
    lib.wrms_set_frame_size.restype = c_int

    lib.wrms_set_track.argtypes = [c_void_p, c_char_p, c_size_t]
    lib.wrms_set_track.restype = c_int

    c_engine = lib.wrms_create()
    if not c_engine:
        raise RuntimeError('wrms_create() failed')
    return c_engine


async def init_track(request):
    body: dict = await request.json()

    hnd = c_ensure_engine()

    lib.wrms_set_frame_size(hnd, body['width'], body['height'])

    content_b = body['content'].encode('utf-8')
    # set/replace track (la lib C ya libera el anterior si existía)
    rc = lib.wrms_set_track(hnd, content_b, len(content_b))
    if rc == 0:
        # TODO: prebuffer [0..quantity_ms] step step_ms:
        #   - llamar wrms_render_a8(t_ms)
        #   - componer sprites en RGBA
        #   - encode WebP en Python
        #   - base64 -> webp_b64

        out = JSONResponse({'frames': []})
    else:
        out = JSONResponse({'frames': [], 'ok': False, 'error': f'wrms_set_track rc={rc}'}, status_code=400)
    return out


async def render_frame(request):
    # body: dict = await request.json()
    # TODO: render frame with libass, return webp bytes (image/webp) or 204 if nothing
    return Response(status_code=200)


async def health(request):
    return JSONResponse({'ok': True})


app = Starlette(routes=[
    Route('/health', health, methods=['GET']),
    Route('/init', init_track, methods=['POST']),
    Route('/render', render_frame, methods=['POST']),
])


def get_ip_for(dst_ip: str) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((dst_ip, 9))
        ip = s.getsockname()[0]
    except OSError:
        ip = None
    finally:
        s.close()
    return ip


def discovery_loop():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', DISCOVERY_PORT))

    while True:
        data, (src_ip, src_port) = sock.recvfrom(2048)
        msg = data.decode('utf-8', errors='ignore').strip()

        if msg == 'WRMS_DISCOVERY_V1':
            ip = get_ip_for(src_ip)
            if ip:
                reply = json.dumps({
                    'ip': ip,
                    'port': APP_PORT,
                    'name': socket.gethostname()
                })
                sock.sendto(reply.encode('utf-8'), (src_ip, src_port))


def main():
    t = threading.Thread(target=discovery_loop, daemon=True)
    t.start()
    uvicorn.run(app, host='0.0.0.0', port=APP_PORT, log_level='info')


if __name__ == '__main__':
    main()
