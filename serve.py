"""P Studio preview and local Windows desktop-pet bridge."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen
import webbrowser
from desktop_host import APP_ID, DesktopManager, process_lock, validate_state

ROOT = Path(__file__).resolve().parent

def local_origin(origin):
    """Permit browser previews on loopback; never expose the bridge to remote sites."""
    if not origin:
        return True
    try:
        parsed = urlsplit(origin)
        return (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost')
                and parsed.username is None and parsed.password is None
                and not parsed.path and not parsed.query and not parsed.fragment
                and parsed.port is not None and 0 < parsed.port <= 65535)
    except ValueError:
        return False

class StudioServer(ThreadingHTTPServer):
    allow_reuse_address = True

class StudioHandler(SimpleHTTPRequestHandler):
    manager = DesktopManager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def json_response(self, status, value):
        data = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.preview_headers()
        self.end_headers()
        self.wfile.write(data)

    def preview_headers(self):
        origin = self.headers.get('Origin')
        if origin and local_origin(origin):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')

    def local_request(self):
        expected = {'127.0.0.1:' + str(self.server.server_port), 'localhost:' + str(self.server.server_port)}
        return self.headers.get('Host') in expected and local_origin(self.headers.get('Origin'))

    def do_OPTIONS(self):
        if urlsplit(self.path).path not in ('/api/pet/status', '/api/pet/summon', '/api/pet/state'):
            self.json_response(404, {'ok': False})
            return
        if not self.local_request():
            self.json_response(403, {'ok': False, 'message': 'Local access only'})
            return
        self.send_response(204)
        self.preview_headers()
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        if urlsplit(self.path).path == '/api/pet/status':
            if not self.local_request():
                self.json_response(403, {'ok': False, 'message': 'Local access only'})
                return
            self.json_response(200, self.manager.status())
        else:
            super().do_GET()

    def do_POST(self):
        route = urlsplit(self.path).path
        if route not in ('/api/pet/summon', '/api/pet/state'):
            self.json_response(404, {'ok': False})
            return
        if not self.local_request() or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.json_response(403, {'ok': False, 'message': 'Local JSON requests only'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('Invalid payload size')
            state = validate_state(json.loads(self.rfile.read(length)))
            result = self.manager.summon(state) if route.endswith('/summon') else self.manager.update(state)
            self.json_response(200, result)
        except (ValueError, UnicodeError) as error:
            self.json_response(400, {'ok': False, 'message': str(error)})
        except RuntimeError as error:
            self.json_response(503, {'ok': False, 'message': str(error)})
        except OSError:
            logging.exception('Desktop pet launch failed')
            self.json_response(503, {'ok': False, 'message': '桌宠启动失败，请重新运行 start.bat 后重试。'})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    options = parser.parse_args()
    try:
        with process_lock('studio-server'), StudioServer(('127.0.0.1', 8086), StudioHandler) as server:
            url = 'http://127.0.0.1:8086'
            print(f'P Studio: {url}\nPress Ctrl+C to stop.', flush=True)
            if not options.no_browser:
                webbrowser.open(url)
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    except OSError as error:
        existing = False
        try:
            with urlopen('http://127.0.0.1:8086/api/pet/status', timeout=2) as response:
                existing = json.load(response).get('app_id') == APP_ID
        except (OSError, ValueError):
            pass
        if existing:
            print('P Studio is already running: http://127.0.0.1:8086')
            if not options.no_browser:
                webbrowser.open('http://127.0.0.1:8086')
        else:
            print(f'Unable to start port 8086: {error}')
            print('Close an older preview server and run start.bat again.')
            raise SystemExit(1)
