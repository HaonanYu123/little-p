"""Local-only launcher/control bridge for the P Studio desktop companion."""
from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from runtime_paths import data_root, resource_root

ROOT = resource_root()
DATA_ROOT = data_root()
APP_ID = 'little-p-desktop-v1'
CONTROL_PORT = 39737
EMOTIONS = tuple(f'{i:02d}' for i in (*range(8), *range(10, 22), *range(30, 42)))
DEFAULT_STATE = dict(character='pink-robot', emotion='02', sketch=False, lang='zh', theme='light')

class InstanceRunningError(OSError):
    pass

@contextmanager
def process_lock(name):
    """A process-lifetime lock, released automatically even after a crash."""
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    with (DATA_ROOT / (name + '.lock')).open('a+b') as lock:
        lock.seek(0, 2)
        if not lock.tell():
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise InstanceRunningError('P Studio instance is already running') from error
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == 'nt':
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

def validate_state(value):
    if not isinstance(value, dict):
        raise ValueError('State must be a JSON object')
    state = {key: value.get(key, default) for key, default in DEFAULT_STATE.items()}
    if state['character'] not in ('robot', 'pink-robot') or state['emotion'] not in EMOTIONS:
        raise ValueError('Unknown character or emotion')
    if type(state['sketch']) is not bool or state['lang'] not in ('zh', 'en') or state['theme'] not in ('light', 'dark'):
        raise ValueError('Invalid presentation settings')
    return state

def request_pet(action, state=None, timeout=1):
    payload = {'app_id': APP_ID, 'action': action}
    if state is not None:
        payload['state'] = validate_state(state)
    try:
        with socket.create_connection(('127.0.0.1', CONTROL_PORT), timeout=timeout) as stream:
            stream.settimeout(timeout)
            stream.sendall(json.dumps(payload).encode('utf-8') + b'\n')
            response = json.loads(stream.makefile('rb').readline(8193))
            if response.get('app_id') == APP_ID:
                return response
    except (OSError, ValueError):
        pass
    return None

class DesktopManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.process = None

    def status(self):
        return request_pet('status') or {'app_id': APP_ID, 'ok': True, 'active': False}

    def update(self, state):
        return request_pet('update', state) or {'ok': True, 'active': False}

    def summon(self, state):
        state = validate_state(state)
        with self._lock:
            existing = request_pet('summon', state)
            if existing and existing.get('ready'):
                return existing
            if not existing:
                if os.name != 'nt':
                    raise RuntimeError('桌面召唤当前支持 Windows。')
                try:
                    available = importlib.util.find_spec('PyQt5.QtWebEngineWidgets') is not None
                except ModuleNotFoundError:
                    available = False
                if not available:
                    raise RuntimeError('请先双击 install-desktop.bat 安装桌宠组件，然后重新召唤。')
                pythonw = Path(sys.executable).with_name('pythonw.exe')
                executable = str(pythonw) if pythonw.exists() else sys.executable
                DATA_ROOT.mkdir(parents=True, exist_ok=True)
                with (DATA_ROOT / 'desktop-pet.log').open('ab') as log:
                    self.process = subprocess.Popen(
                        [executable, str(ROOT / 'desktop' / 'pet.py'), '--state', json.dumps(state)],
                        cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
            deadline = time.monotonic() + 18
            while time.monotonic() < deadline:
                result = request_pet('status', timeout=.5)
                if result and result.get('ready'):
                    return result
                if self.process is not None and self.process.poll() is not None:
                    raise RuntimeError('桌宠启动失败，详情保存在 output/desktop-pet.log。')
                time.sleep(.12)
            raise RuntimeError('桌宠仍在启动，请稍后再次点击召唤。')
