
import socket
import threading
import json
import uvicorn
from ctypes import c_void_p, c_int, c_size_t, c_char_p, c_uint8, POINTER
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.middleware.cors import CORSMiddleware

from .tools import load_default_font, parse_ass_events, encode_subs
from .libass_bind import lib, find_lib_file
from .libass_render import WrmsFrame, render_frame_to_webp

APP_PORT = 19090
DISCOVERY_PORT = 19091

c_engine = None
event_list = []


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

    lib.wrms_add_font_mem.argtypes = [c_void_p, c_char_p, POINTER(c_uint8), c_size_t]
    lib.wrms_add_font_mem.restype = c_int

    lib.wrms_set_default_font.argtypes = [c_void_p, c_char_p]
    lib.wrms_set_default_font.restype = c_int

    c_engine = lib.wrms_create()
    if not c_engine:
        raise RuntimeError('wrms_create() failed')

    font_path = find_lib_file('default.woff2')
    font_name = load_default_font(lib, c_engine, font_path, 'default')
    print(f'default font {font_name}')
    rc = lib.wrms_set_default_font(c_engine, font_name.encode('utf-8'))
    if rc != 0:
        raise RuntimeError('wrms_set_default_font rc=%s' % rc)

    return c_engine


async def init_track(request):
    body: dict = await request.json()
    print(f'init_track {body["subName"]}')
    hnd = c_ensure_engine()

    content_b = body['content'].encode('utf-8')
    rc = lib.wrms_set_track(hnd, content_b, len(content_b))

    event_list.clear()
    event_list.extend(parse_ass_events(body['content']))

    if rc == 0:
        out = JSONResponse({'events': event_list})
    else:
        out = JSONResponse({'events': [], 'error': f'wrms_set_track rc={rc}'}, status_code=400)

    print(f'init_track {body["subName"]} {out.status_code} {len(event_list)}')
    return out


async def init_render(request):
    body: dict = await request.json()
    print(f'init_render {body["subName"]} tms={body["quantityMs"]}')

    hnd = c_ensure_engine()

    lib.wrms_set_frame_size(hnd, body['width'], body['height'])

    event_index = body['initEvent']
    duration = 0
    sub_list = []
    while duration < body['quantityMs'] and event_index < len(event_list):
        ev = event_list[event_index]
        print(f'init_render {body["subName"]} i={event_index} id={ev["id"]}')
        if ev['type'] == 'static':
            webp = render_frame_to_webp(lib, hnd, body['width'], body['height'], ev['start_ms'])
        else:
            webp = None
        sub_list.append({'id': ev['id'], 'data': webp})
        event_index += 1
        duration += ev['dur_ms']

    print(f'init_render {body["subName"]} tms={body["quantityMs"]} size={len(sub_list)} end')
    return Response(bytes(encode_subs(sub_list)), media_type='application/octet-stream', status_code=200)


async def render_frame(request):
    body: dict = await request.json()

    print(f'render_frame {body["subName"]} {body["eventIndexList"][0]}')

    hnd = c_ensure_engine()
    lib.wrms_set_frame_size(hnd, body['width'], body['height'])

    sub_list = []
    for event_index in body['eventIndexList']:
        ev = event_list[event_index]
        print(f'render_frame {body["subName"]} i={event_index} id={ev["id"]}')
        if ev['type'] == 'static':
            webp = render_frame_to_webp(lib, hnd, body['width'], body['height'], ev['start_ms'])
        else:
            webp = None
        sub_list.append({'id': ev['id'], 'data': webp})
        event_index += 1

    print(f'render_frame {body["subName"]} {body["eventIndexList"][0]} size={len(sub_list)} end')
    return Response(bytes(encode_subs(sub_list)), media_type='application/octet-stream', status_code=200)


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
    Route('/health', health, methods=['GET', 'OPTIONS']),
    Route('/init', init_track, methods=['POST', 'OPTIONS']),
    Route('/initRender', init_render, methods=['POST', 'OPTIONS']),
    Route('/render', render_frame, methods=['POST', 'OPTIONS']),
    Route('/destroy', destroy, methods=['POST', 'OPTIONS']),
])

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
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
