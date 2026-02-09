
import socket
import threading
import json
import uvicorn
import base64
from ctypes import c_void_p, c_int, c_size_t, c_char_p, POINTER
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.middleware.cors import CORSMiddleware

from .libass_bind import lib
from .libass_render import WrmsFrame, render_frame_to_webp

APP_PORT = 19090
DISCOVERY_PORT = 19091

c_engine = None


def c_ensure_engine():
    global c_engine
    if c_engine is not None:
        return c_engine

    # engine lifecycle
    lib.wrms_create.argtypes = []
    lib.wrms_create.restype = c_void_p

    lib.wrms_destroy.argtypes = [c_void_p]
    lib.wrms_destroy.restype = None

    # config
    lib.wrms_set_frame_size.argtypes = [c_void_p, c_int, c_int]
    lib.wrms_set_frame_size.restype = c_int

    lib.wrms_set_track.argtypes = [c_void_p, c_char_p, c_size_t]
    lib.wrms_set_track.restype = c_int

    # render + free frame
    lib.wrms_render_a8.argtypes = [c_void_p, c_int, POINTER(WrmsFrame)]
    lib.wrms_render_a8.restype = c_int

    lib.wrms_free_frame.argtypes = [POINTER(WrmsFrame)]
    lib.wrms_free_frame.restype = None

    c_engine = lib.wrms_create()
    if not c_engine:
        raise RuntimeError('wrms_create() failed')
    return c_engine


async def init_track(request):
    body: dict = await request.json()

    print(f'init_track {body["subName"]}')

    hnd = c_ensure_engine()

    lib.wrms_set_frame_size(hnd, body['width'], body['height'])

    content_b = body['content'].encode('utf-8')
    rc = lib.wrms_set_track(hnd, content_b, len(content_b))
    if rc == 0:
        frames = []
        t = 0
        while t <= body['quantityMs']:
            webp = render_frame_to_webp(lib, hnd, body['width'], body['height'], t)
            frames.append({
                't_ms': t,
                'data': webp and base64.b64encode(webp).decode('ascii') or None,
            })
            t += body['stepMs']

        out = JSONResponse({'frames': frames})
    else:
        out = JSONResponse({'frames': [], 'error': f'wrms_set_track rc={rc}'}, status_code=400)
    return out


async def render_frame(request):
    body: dict = await request.json()

    print(f'render_frame {body["subName"]} ')

    hnd = c_ensure_engine()
    lib.wrms_set_frame_size(hnd, body['width'], body['height'])

    webp = render_frame_to_webp(lib, hnd, body['width'], body['height'], body['tMs'])

    if webp is None:
        out = Response(status_code=204)
    else:
        out = Response(webp, media_type='image/webp', status_code=200)
    print(f'render_frame {body["subName"]} {out.status_code}')
    return out


async def destroy(request):
    body: dict = await request.json()

    print(f'destroy {body["subName"]}')

    global c_engine
    if c_engine is not None:
        lib.wrms_destroy(c_engine)
        c_engine = None
    return JSONResponse({'ok': True})


async def health(request):
    qp: dict = request.query_params

    print(f'health {qp["subName"]}')

    return JSONResponse({'ok': True})

app = Starlette(routes=[
    Route('/health', health, methods=['GET']),
    Route('/init', init_track, methods=['POST']),
    Route('/render', render_frame, methods=['POST']),
    Route('/destroy', destroy, methods=['POST']),
])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


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
