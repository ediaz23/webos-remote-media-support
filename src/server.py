
import os
import socket
import threading
import json
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse


APP_PORT = 19090
DISCOVERY_PORT = 19091

app = FastAPI()

@app.get('/health')
def health():
    return JSONResponse({'ok': True, 'name': 'aja'})

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
