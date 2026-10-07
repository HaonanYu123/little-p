"""Exercise the real Qt picker and shared JS renderer in an isolated pet window."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt5.QtCore import QPoint, QPointF, QTimer, Qt
from PyQt5.QtGui import QWheelEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from desktop.pet import DesktopPet
from desktop_host import DEFAULT_STATE, EMOTIONS

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
app = QApplication(sys.argv[:1])
window = DesktopPet(DEFAULT_STATE, verify=True)
window.verify_timer.stop()
results = []
failures = []
menu_size = None


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    results.append(name)


def finish(error=None):
    if error:
        failures.append(str(error))
    report = dict(passed=len(results), results=results, failures=failures, menu_size=menu_size)
    (ROOT / 'output' / 'desktop-menu-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True), flush=True)
    window.close()
    app.exit(1 if failures else 0)


def query(callback):
    window.page.runJavaScript('({character:PET_ENGINE.character.id,emotion:PET_ENGINE.emotionId})', callback)


def later(callback):
    def wrapped(value):
        try:
            callback(value)
        except Exception as error:
            finish(error)
    QTimer.singleShot(80, lambda: query(wrapped))


def expressions(index=0):
    if index == len(window.emotions):
        check('All 32 expression buttons reach the live renderer', True)
        QTest.mouseClick(window.menu.style_button, Qt.LeftButton)
        later(check_style)
        return
    emotion = window.emotions[index]
    QTest.mouseClick(window.menu.tabs[emotion['group']], Qt.LeftButton)
    QTest.mouseClick(window.menu.buttons[emotion['id']], Qt.LeftButton)

    def received(state):
        assert state['emotion'] == emotion['id'], f"Expression {emotion['id']} did not reach JS"
        assert window.state['emotion'] == emotion['id']
        assert window.menu.buttons[emotion['id']].property('selected')
        assert window.menu.isVisible(), 'Picking closed the panel'
        expressions(index + 1)
    later(received)


def check_style(state):
    check('Switch style updates the live pet', state['character'] == 'robot')
    check('Switch style preserves the current expression', state['emotion'] == '41')
    check('Panel remains open while comparing styles', window.menu.isVisible())
    position = QPointF(140, 100)
    wheel = QWheelEvent(position, QPointF(window.menu.mapToGlobal(QPoint(140, 100))), QPoint(), QPoint(0, -120), Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
    QApplication.sendEvent(window.menu, wheel)
    later(check_wheel)


def check_wheel(state):
    check('Wheel wraps through all 32 expressions', state['emotion'] == '00')
    check('Wheel selects the matching expression tab', window.menu.group == 'life')
    window.menu.buttons['00'].setFocus()
    QTest.keyClick(window.menu.buttons['00'], Qt.Key_Right)
    later(check_keyboard)


def check_keyboard(state):
    check('Arrow key switches expressions without the website', state['emotion'] == '01')
    QTest.keyClick(window.menu.buttons['01'], Qt.Key_Escape)
    check('Escape closes the panel and keeps the pet visible', not window.menu.isVisible() and window.isVisible())
    area = QApplication.primaryScreen().availableGeometry()
    window.menu.popup(area.bottomRight())
    check('Popup stays inside the monitor at the bottom-right edge', area.contains(window.menu.geometry()))
    window.change_state(emotion='10', theme='dark', lang='en')
    QTimer.singleShot(120, final_checks)


def final_checks():
    try:
        check('Menu follows dark theme and English labels', window.menu.theme == 'dark' and window.menu.title.text() == 'Classic P')
        window.menu.select_group('emotion')
        window.menu.grab().save(str(ROOT / 'output' / 'desktop-menu-dark.png'))
        window.change_state(emotion='02', theme='light', lang='zh')
        window.menu.select_group('emotion')
        window.menu.grab().save(str(ROOT / 'output' / 'desktop-menu-emotions.png'))
        window.menu.select_group('life')
        window.menu.grab().save(str(ROOT / 'output' / 'desktop-menu-daily.png'))
        daily_height = window.menu.height()
        window.menu.select_group('agent')
        check('Daily group collapses empty space and larger groups remain compact', daily_height < window.menu.height() <= 275)
        check('Eye previews come from the shared expression catalog', all(e.get('eye') and not window.menu.buttons[e['id']].icon().isNull() for e in window.emotions))
        check('All expression labels have readable full names', all(window.menu.buttons[e['id']].accessibleName() == e['name'] for e in window.emotions))
        window.menu.grab().save(str(ROOT / 'output' / 'desktop-menu-work.png'))
        image = window.menu.grab().toImage()
        check('Popup background stays opaque over the desktop', image.pixelColor(image.width() // 2, 12).alpha() > 240)
        check('Only switch-style and dismiss actions remain', window.menu.style_button.text() == '切换样式' and window.menu.dismiss_button.text() == '收起')
        window.change_state(character='pink-robot', emotion='14')
        window.menu.select_group('emotion')
        window.menu.grab().save(str(ROOT / 'output' / 'desktop-menu-pink.png'))
        check('Character portrait and current expression follow style changes', window.menu.title.text() == '蝴蝶结小 P' and window.menu.hint.toolTip() == window.menu.buttons['14'].toolTip() and not window.menu.avatar.pixmap().isNull())
        QTest.mouseClick(window.menu.dismiss_button, Qt.LeftButton)
        check('Dismiss closes the native pet', not window.isVisible())
        finish()
    except Exception as error:
        finish(error)


def start():
    global menu_size
    if not window.is_ready or not window.menu:
        QTimer.singleShot(80, start)
        return
    try:
        check('Menu catalog contains exactly the shared 32 expressions', {e['id'] for e in window.emotions} == set(EMOTIONS))
        check('All groups are complete (8 daily, 12 feelings, 12 work)', [sum(e['group'] == g for e in window.emotions) for g in window.menu.GROUPS] == [8, 12, 12])
        window.show_menu()
        menu_size = [window.menu.width(), window.menu.height()]
        check('Popup is compact (282px wide and under 275px high)', menu_size[0] == 282 and menu_size[1] <= 275)
        check('Current expression is selected on open', window.menu.buttons['02'].property('selected'))
        check('Popup uses three columns', window.menu.grid.columnCount() == 3)
        expressions()
    except Exception as error:
        finish(error)


QTimer.singleShot(80, start)
QTimer.singleShot(25000, lambda: finish('Menu verification timed out'))
sys.exit(app.exec_())
