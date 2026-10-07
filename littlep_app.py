"""Installed Little P entry point and littlep:// protocol handler."""
import argparse
import json
import os
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from runtime_paths import resource_root

ROOT = resource_root()
if getattr(sys, 'frozen', False):
    os.environ.setdefault(
        'QTWEBENGINEPROCESS_PATH',
        str(ROOT / 'PyQt5' / 'Qt5' / 'bin' / 'QtWebEngineProcess.exe'),
    )

from PyQt5.QtCore import QObject, QTimer, QUrl, Qt, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QApplication, QMessageBox

from desktop.pet import DesktopPet
from desktop_host import DEFAULT_STATE, InstanceRunningError, process_lock, request_pet, validate_state


def read_text(name, default=''):
    try:
        return (ROOT / name).read_text(encoding='utf-8').strip()
    except OSError:
        return default


VERSION = read_text('VERSION', '0.0.0')


def summon_running_pet(state, wait_seconds=0):
    """Deliver a summon to an existing instance, including one still starting."""
    deadline = time.monotonic() + max(0, wait_seconds)
    while True:
        response = request_pet('summon', state, timeout=.45)
        if response:
            return response
        if time.monotonic() >= deadline:
            return None
        time.sleep(.12)


def protocol_state(value):
    state = dict(DEFAULT_STATE)
    if not value:
        return state
    parsed = urlsplit(value)
    if parsed.scheme.lower() != 'littlep' or parsed.netloc.lower() not in ('summon', 'open'):
        raise ValueError('Unsupported Little P link')
    query = parse_qs(parsed.query)
    for key in ('character', 'emotion', 'lang', 'theme'):
        if key in query:
            state[key] = query[key][0]
    if 'sketch' in query:
        state['sketch'] = query['sketch'][0].lower() in ('1', 'true', 'yes')
    return validate_state(state)


def version_key(value):
    try:
        return tuple(int(part) for part in value.split('.')[:3])
    except (AttributeError, TypeError, ValueError):
        return (0, 0, 0)


class UpdateCheck(QObject):
    available = pyqtSignal(dict)

    def start(self):
        try:
            config = json.loads(read_text('distribution.json', '{}'))
            manifest_url = config.get('update_manifest_url', '').strip()
        except (ValueError, AttributeError):
            return
        if not manifest_url:
            return

        def fetch():
            try:
                with urlopen(manifest_url, timeout=4) as response:
                    manifest = json.load(response)
                if version_key(manifest.get('version')) > version_key(VERSION):
                    self.available.emit(manifest)
            except (OSError, ValueError, TypeError):
                pass

        threading.Thread(target=fetch, daemon=True).start()


def offer_update(manifest):
    text = 'Little P 有新版本 {}。\n\n{}'.format(manifest.get('version', ''), manifest.get('notes', ''))
    if QMessageBox.question(None, 'Little P 更新', text + '\n\n现在打开下载页面吗？') == QMessageBox.Yes:
        url = manifest.get('download_url', '')
        if url:
            QDesktopServices.openUrl(QUrl(url))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('link', nargs='?')
    parser.add_argument('--version', action='store_true')
    args = parser.parse_args()
    if args.version:
        print(VERSION)
        return 0
    try:
        state = protocol_state(args.link)
    except ValueError:
        state = dict(DEFAULT_STATE)
    existing = summon_running_pet(state)
    if existing:
        return 0
    for attempt in range(2):
        try:
            with process_lock('desktop-pet'):
                QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
                QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
                app = QApplication(sys.argv[:1])
                app.setApplicationName('Little P')
                window = DesktopPet(state)
                updates = UpdateCheck()
                updates.available.connect(offer_update)
                QTimer.singleShot(1200, updates.start)
                app._update_check = updates
                app._pet_window = window
                return app.exec_()
        except InstanceRunningError:
            # Another protocol click may have started the process milliseconds
            # earlier. Wait for its control server instead of silently exiting.
            if summon_running_pet(state, wait_seconds=15):
                return 0
            if attempt == 1:
                return 1
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
