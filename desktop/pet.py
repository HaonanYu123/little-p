"""Transparent, frameless Windows companion; renders the existing JS engine."""
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import socketserver
import sys
import threading

SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT))
from runtime_paths import data_root, resource_root
ROOT = resource_root()
DATA_ROOT = data_root()
from desktop_host import APP_ID, CONTROL_PORT, DEFAULT_STATE, EMOTIONS, InstanceRunningError, process_lock, request_pet, validate_state
from PyQt5.QtCore import QFile, QIODevice, QObject, QPoint, QTimer, QUrl, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QCursor, QIcon
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from PyQt5.QtWebChannel import QWebChannel
from desktop.menu import PetMenu


class PetPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        if level == QWebEnginePage.ErrorMessageLevel:
            print(f'JS error {source}:{line}: {message}', flush=True)

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        return url.isLocalFile() and Path(url.toLocalFile()).resolve().is_relative_to(ROOT)


class Bridge(QObject):
    stateChanged = pyqtSignal(str)

    def __init__(self, window):
        super().__init__(window)
        self.window = window

    @pyqtSlot(result=str)
    def initialState(self):
        return json.dumps(self.window.state)

    @pyqtSlot()
    def ready(self):
        self.window.is_ready = True
        self.window.show()

    @pyqtSlot(str)
    def changed(self, text):
        try:
            self.window.state = validate_state(json.loads(text))
            self.window.sync_menu()
        except ValueError:
            pass

    @pyqtSlot(str)
    def catalogReady(self, text):
        try:
            values = json.loads(text)
            if not isinstance(values, list) or len(values) != len(EMOTIONS):
                raise ValueError('Invalid expression catalog')
            if {value['id'] for value in values} != set(EMOTIONS):
                raise ValueError('Invalid expression IDs')
            for value in values:
                if value['group'] not in PetMenu.GROUPS or not all(isinstance(value[k], str) for k in ('id', 'name', 'en')):
                    raise ValueError('Invalid expression labels')
            self.window.emotions = values
            self.window.menu = PetMenu(self.window, values)
        except (ValueError, KeyError, TypeError):
            print('Invalid desktop expression catalog', flush=True)

    @pyqtSlot()
    def dragStart(self):
        self.window.drag_origin = (QCursor.pos(), self.window.pos())

    @pyqtSlot()
    def dragMove(self):
        if self.window.drag_origin:
            cursor, position = self.window.drag_origin
            self.window.move(position + QCursor.pos() - cursor)

    @pyqtSlot()
    def dragEnd(self):
        self.window.drag_origin = None
        self.window.keep_on_screen()

    @pyqtSlot()
    def showMenu(self):
        self.window.show_menu()

    @pyqtSlot()
    def dismiss(self):
        self.window.close()


class ControlServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class DesktopPet(QWidget):
    controlReceived = pyqtSignal(dict)

    def __init__(self, initial_state, verify=False):
        super().__init__()
        self.state = validate_state(initial_state)
        self.is_ready = False
        self.drag_origin = None
        self.menu = None
        self.emotions = []
        self.verify = verify
        self.setWindowTitle('P Studio Desktop Pet')
        self.setWindowIcon(QIcon(str(ROOT / 'assets' / 'favicon.svg')))
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.resize(155, 155)
        self.setMinimumSize(110, 110)
        self.setStyleSheet('background: transparent;')
        self.view = QWebEngineView(self)
        self.view.setAttribute(Qt.WA_TranslucentBackground)
        self.page = PetPage(self.view)
        self.page.setBackgroundColor(QColor(0, 0, 0, 0))
        self.view.setPage(self.page)
        self.view.setContextMenuPolicy(Qt.NoContextMenu)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.channel = QWebChannel(self.page)
        self.bridge = Bridge(self)
        self.channel.registerObject('desktop', self.bridge)
        self.page.setWebChannel(self.channel)
        self.view.loadFinished.connect(self.on_load)
        self.controlReceived.connect(self.on_control)
        available = QApplication.primaryScreen().availableGeometry()
        self.move(available.right() - self.width() - 35, available.bottom() - self.height() - 35)
        self.start_control_server()
        self.view.load(QUrl.fromLocalFile(str(ROOT / 'desktop' / 'pet.html')))
        self.gaze_timer = QTimer(self)
        self.gaze_timer.timeout.connect(self.update_gaze)
        self.gaze_timer.start(70)
        self.show()
        if verify:
            self.verify_timer = QTimer(self)
            self.verify_timer.timeout.connect(self.start_verify)
            self.verify_timer.start(300)

    def on_load(self, success):
        if not success:
            print('Desktop page failed to load', flush=True)
            return
        channel_js = QFile(':/qtwebchannel/qwebchannel.js')
        if not channel_js.open(QIODevice.ReadOnly):
            print('Missing Qt WebChannel runtime', flush=True)
            return
        script = bytes(channel_js.readAll()).decode('utf-8')
        channel_js.close()
        self.page.runJavaScript(script + '\nwindow.connectDesktopBridge();')

    def start_control_server(self):
        window = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(2)
                try:
                    message = json.loads(self.rfile.readline(8193))
                    if not isinstance(message, dict) or message.get('app_id') != APP_ID:
                        return
                    action = message.get('action')
                    if action not in ('status', 'update', 'summon', 'dismiss'):
                        return
                    if action in ('update', 'summon'):
                        message['state'] = validate_state(message.get('state'))
                    if action != 'status':
                        window.controlReceived.emit(message)
                    response = dict(app_id=APP_ID, ok=True, active=True, ready=window.is_ready, pid=os.getpid(), state=window.state, native_size=[window.width(), window.height()])
                    self.wfile.write(json.dumps(response).encode('utf-8') + b'\n')
                except (ValueError, OSError):
                    return

        self.control_server = ControlServer(('127.0.0.1', 0 if self.verify else CONTROL_PORT), Handler)
        self.control_thread = threading.Thread(target=self.control_server.serve_forever, daemon=True)
        self.control_thread.start()

    def on_control(self, message):
        if message['action'] == 'dismiss':
            self.close()
            return
        self.state = message['state']
        self.sync_menu()
        if self.is_ready:
            self.bridge.stateChanged.emit(json.dumps(self.state))
        if message['action'] == 'summon':
            self.show()
            self.raise_()
            self.keep_on_screen()

    def update_gaze(self):
        if not self.is_ready or self.drag_origin:
            return
        cursor = QCursor.pos() - self.pos()
        x = max(-1, min(1, (cursor.x() - self.width() / 2) / (self.width() * .6)))
        y = max(-1, min(1, (cursor.y() - self.height() / 2) / (self.height() * .6)))
        self.page.runJavaScript(f'if(window.PET_ENGINE)PET_ENGINE.setGaze({x:.3f},{y:.3f});')

    def keep_on_screen(self):
        screen = QApplication.screenAt(self.pos() + QPoint(self.width() // 2, self.height() // 2)) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(max(area.left(), min(self.x(), area.right() - self.width() + 1)), max(area.top(), min(self.y(), area.bottom() - self.height() + 1)))

    def change_state(self, **values):
        self.state = validate_state(dict(self.state, **values))
        self.sync_menu()
        self.bridge.stateChanged.emit(json.dumps(self.state))

    def sync_menu(self):
        if self.menu:
            self.menu.sync_state()

    def cycle_emotion(self, delta):
        index = EMOTIONS.index(self.state['emotion'])
        self.change_state(emotion=EMOTIONS[(index + delta) % len(EMOTIONS)])

    def show_menu(self):
        if self.menu:
            self.menu.popup()

    def start_verify(self):
        if self.is_ready:
            self.verify_timer.stop()
            QTimer.singleShot(3400, self.finish_verify)

    def finish_verify(self):
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        self.view.grab().save(str(DATA_ROOT / 'desktop-native.png'))
        self.page.runJavaScript("({character:PET_ENGINE.character.id,emotion:PET_ENGINE.emotionId,states:MoodMates.config.list().length,texture:document.querySelector('.robot-texture').getAttribute('href'),bodyBackground:getComputedStyle(document.body).backgroundColor})", self.write_verify)

    def write_verify(self, web_state):
        report = dict(visible=self.isVisible(), frameless=bool(self.windowFlags() & Qt.FramelessWindowHint), topmost=bool(self.windowFlags() & Qt.WindowStaysOnTopHint), translucent=self.testAttribute(Qt.WA_TranslucentBackground), page_alpha=self.page.backgroundColor().alpha(), native_size=[self.width(), self.height()], web_state=web_state)
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        (DATA_ROOT / 'desktop-native-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report), flush=True)
        self.close()

    def closeEvent(self, event):
        self.is_ready = False
        if self.menu:
            self.menu.hide()
        self.gaze_timer.stop()
        self.control_server.shutdown()
        self.control_server.server_close()
        event.accept()
        QApplication.instance().quit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', default=json.dumps(DEFAULT_STATE))
    parser.add_argument('--verify', action='store_true')
    arguments = parser.parse_args()
    if not arguments.verify and request_pet('summon', validate_state(json.loads(arguments.state))):
        print('Desktop pet is already running.', flush=True)
        sys.exit(0)
    try:
        with (nullcontext() if arguments.verify else process_lock('desktop-pet')):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
            app = QApplication(sys.argv[:1])
            window = DesktopPet(validate_state(json.loads(arguments.state)), verify=arguments.verify)
            QTimer.singleShot(25000, app.quit) if arguments.verify else None
            result = app.exec_()
        sys.exit(result)
    except InstanceRunningError:
        print('Desktop pet is already starting.', flush=True)
