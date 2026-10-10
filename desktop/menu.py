"""Small desktop expression palette, using the shared catalog for every label and eye."""
from math import ceil
from pathlib import Path
from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QCursor, QIcon, QKeySequence, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import QApplication, QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QShortcut, QVBoxLayout, QWidget
from runtime_paths import resource_root

ROOT = resource_root()


def paint_eyes(painter, eye, color, center=(12, 12), scale=1):
    painter.save()
    painter.translate(*center)
    painter.scale(scale, scale)
    painter.translate(-12, -12)
    ink = QColor(color)
    painter.setPen(QPen(ink, 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)
    for x in (6.5, 13.5):
        if eye.startswith(('closed', 'sleepy')):
            painter.drawLine(QRectF(x, 12, 4, 0).topLeft(), QRectF(x, 12, 4, 0).topRight())
        elif eye.startswith('happy'):
            path = QPainterPath()
            path.moveTo(x, 13)
            path.quadTo(x + 2, 9, x + 4, 13)
            painter.drawPath(path)
        elif eye.startswith(('angry', 'sad', 'squint')):
            tilt = -1.4 if eye.startswith('sad') else 1.4
            if x > 10:
                tilt = -tilt
            painter.drawLine(QRectF(x, 10.5, 0, 0).topLeft(), QRectF(x + 4, 10.5 + tilt, 0, 0).topLeft())
            painter.drawEllipse(QRectF(x + 1.2, 13, 1.5, 2))
        elif eye.startswith('scan'):
            painter.drawLine(QRectF(x, 12, 0, 0).topLeft(), QRectF(x + 4, 12, 0, 0).topLeft())
            painter.drawLine(QRectF(x + 2, 10, 0, 0).topLeft(), QRectF(x + 2, 14, 0, 0).topLeft())
        else:
            height = 6 if eye.startswith('wide') else 4
            painter.setBrush(ink)
            painter.drawEllipse(QRectF(x + 1, 12 - height / 2, 2.2, height))
            painter.setBrush(Qt.NoBrush)
    if eye.startswith('shy'):
        painter.drawLine(QRectF(5, 16, 0, 0).topLeft(), QRectF(7, 15, 0, 0).topLeft())
        painter.drawLine(QRectF(17, 16, 0, 0).topLeft(), QRectF(19, 15, 0, 0).topLeft())
    painter.restore()


def face_icon(eye, color):
    """A quiet, readable eye sketch; its shape comes from the engine catalog."""
    pixmap = QPixmap(48, 48)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    ink = QColor(color)
    painter.setPen(QPen(ink, 1.15, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(QRectF(2, 3, 20, 18), 7, 7)
    paint_eyes(painter, eye, color)
    painter.end()
    return QIcon(pixmap)


class PetMenu(QFrame):
    GROUPS = ('life', 'emotion', 'agent')

    def __init__(self, pet, emotions):
        super().__init__(pet, Qt.Popup | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.pet, self.emotions = pet, emotions
        self.group = 'life'
        self.language = self.theme = self.character = None
        self.portrait_state = None
        self.setObjectName('petMenu')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(282)
        self.setFocusPolicy(Qt.StrongFocus)
        self.shortcuts = []
        for key, callback in ((Qt.Key_Escape, self.hide), (Qt.Key_Left, lambda: self.step(-1)), (Qt.Key_Right, lambda: self.step(1))):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 14, 15, 14)
        layout.setSpacing(6)
        heading = QHBoxLayout()
        heading.setSpacing(7)
        self.avatar = QLabel(self)
        self.avatar.setFixedSize(28, 28)
        self.title = QLabel(self)
        self.title.setObjectName('menuTitle')
        self.hint = QLabel(self)
        self.hint.setObjectName('menuHint')
        heading.addWidget(self.avatar)
        heading.addWidget(self.title)
        heading.addStretch()
        heading.addWidget(self.hint)
        layout.addLayout(heading)
        tabs = QHBoxLayout()
        tabs.setSpacing(8)
        self.tabs = {}
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        for group in self.GROUPS:
            button = QPushButton(self)
            button.setProperty('role', 'tab')
            button.setCheckable(True)
            button.setFixedHeight(26)
            button.clicked.connect(lambda checked=False, g=group: self.select_group(g))
            self.tab_group.addButton(button)
            self.tabs[group] = button
            tabs.addWidget(button)
        layout.addLayout(tabs)
        self.grid_host = QWidget(self)
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 2, 0, 2)
        self.grid.setHorizontalSpacing(3)
        self.grid.setVerticalSpacing(3)
        self.grid.setAlignment(Qt.AlignTop)
        for column in range(3):
            self.grid.setColumnStretch(column, 1)
        self.buttons = {}
        for emotion in emotions:
            button = QPushButton(self.grid_host)
            button.setProperty('role', 'emotion')
            button.setProperty('selected', False)
            button.setFixedHeight(29)
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(lambda checked=False, e=emotion['id']: self.pick(e))
            button.hide()
            self.buttons[emotion['id']] = button
        layout.addWidget(self.grid_host)
        divider = QFrame(self)
        divider.setObjectName('menuDivider')
        divider.setFixedHeight(1)
        layout.addWidget(divider)
        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.style_button = QPushButton(self)
        self.style_button.setObjectName('styleButton')
        self.style_button.setFixedHeight(27)
        self.style_button.clicked.connect(self.switch_style)
        self.health_button = QPushButton(self)
        self.health_button.setObjectName('healthButton')
        self.health_button.setFixedHeight(27)
        self.health_button.clicked.connect(self.open_health)
        self.dismiss_button = QPushButton(self)
        self.dismiss_button.setObjectName('dismissButton')
        self.dismiss_button.setFixedHeight(27)
        self.dismiss_button.clicked.connect(self.pet.close)
        footer.addWidget(self.style_button)
        footer.addWidget(self.health_button)
        footer.addStretch()
        self.key_hint = QLabel('↔', self)
        self.key_hint.setObjectName('keyHint')
        footer.addWidget(self.key_hint)
        footer.addStretch()
        footer.addWidget(self.dismiss_button)
        layout.addLayout(footer)
        self.sync_state(select_group=True)

    def sync_state(self, select_group=False):
        state = self.pet.state
        restyle = self.theme != state['theme'] or self.character != state['character']
        if restyle:
            self.theme, self.character = state['theme'], state['character']
            dark = self.theme == 'dark'
            pink = self.character == 'pink-robot'
            surface, text, muted, line, hover = (
                ('#242424', '#efede8', '#aaa6a1', '#42403e', '#333230') if dark else
                ('#fffefb', '#34322f', '#79736e', '#e8e3dc', '#f3f0eb'))
            accent = ('#edb4c3' if pink else '#abcac2') if dark else ('#9b5068' if pink else '#406b61')
            selected_fill = ('#3e3036' if pink else '#2c3b37') if dark else ('#f8edf0' if pink else '#eaf1ee')
            self.panel_surface = QColor(surface)
            self.panel_border = QColor(line)
            self.setStyleSheet(f'''
                QFrame#petMenu {{background:transparent;border:0}}
                QLabel {{background:transparent;color:{text};border:0;font:11px "Microsoft YaHei"}}
                QLabel#menuTitle {{font-size:12px;font-weight:600}}
                QLabel#menuHint {{color:{muted};font-size:10px}}
                QLabel#keyHint {{color:{muted};font-size:11px}}
                QFrame#menuDivider {{background:{line};border:0}}
                QPushButton {{font:11px "Microsoft YaHei";color:{text};background:transparent;border:1px solid transparent;border-radius:5px;padding:0 4px}}
                QPushButton:hover {{background:{hover}}}
                QPushButton:pressed {{background:{line}}}
                QPushButton:focus {{border-color:{muted}}}
                QPushButton[role="tab"] {{color:{muted};border:0;border-bottom:1px solid {line};border-radius:0;padding:0}}
                QPushButton[role="tab"]:checked {{color:{text};border-bottom:2px solid {accent};font-weight:600}}
                QPushButton[role="emotion"] {{text-align:left;padding:0 3px}}
                QPushButton[role="emotion"][selected="true"] {{background:{selected_fill};color:{accent};font-weight:500}}
                QPushButton#styleButton, QPushButton#dismissButton {{color:{muted};font-size:10px;padding:0 6px}}
                QPushButton#styleButton:hover, QPushButton#dismissButton:hover {{color:{text}}}
                QPushButton#healthButton {{color:{accent};background:{selected_fill};border-color:{selected_fill};font-size:10px;font-weight:600;padding:0 7px}}
                QPushButton#healthButton:hover {{border-color:{accent}}}
            ''')
            self.icons = {e['id']: (face_icon(e.get('eye', 'calm'), muted), face_icon(e.get('eye', 'calm'), accent)) for e in self.emotions}
            filename = 'pink-head-soft-oval.png' if pink else 'robot-shell.png'
            image = QPixmap(str(ROOT / 'assets' / 'robot' / filename))
            image = image.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            image.setDevicePixelRatio(2)
            self.portrait_base = image
            self.portrait_state = None
            self.update()
        english = state['lang'] == 'en'
        character = ('Classic P' if state['character'] == 'robot' else 'Ribbon P') if english else (
            '经典小 P' if state['character'] == 'robot' else '蝴蝶结小 P')
        self.title.setText(character)
        current = next(e for e in self.emotions if e['id'] == state['emotion'])
        portrait_state = (state['character'], current.get('eye', 'calm'))
        if self.portrait_state != portrait_state:
            self.portrait_state = portrait_state
            portrait = self.portrait_base.copy()
            painter = QPainter(portrait)
            painter.setRenderHint(QPainter.Antialiasing)
            pink = state['character'] == 'pink-robot'
            paint_eyes(painter, portrait_state[1], '#ffb3d0' if pink else '#aeffff', (14, 16 if pink else 14), .9)
            painter.end()
            self.avatar.setPixmap(portrait)
        label = current['en'] if english else current['name']
        self.hint.setText(self.hint.fontMetrics().elidedText(label, Qt.ElideRight, 90))
        self.hint.setToolTip(label)
        names = ('Daily', 'Feelings', 'Work') if english else ('日常', '情绪', '工作')
        for group, name in zip(self.GROUPS, names):
            count = sum(e['group'] == group for e in self.emotions)
            self.tabs[group].setText(f'{name}  {count}')
        if self.language != state['lang'] or restyle:
            self.language = state['lang']
            for emotion in self.emotions:
                label = emotion['en'] if english else emotion['name']
                button = self.buttons[emotion['id']]
                button.setText(button.fontMetrics().elidedText(label, Qt.ElideRight, 52))
                button.setToolTip(label)
                button.setAccessibleName(label)
        self.style_button.setText('Switch style' if english else '切换样式')
        self.health_button.setText('Health' if english else '健康助手')
        self.dismiss_button.setText('Dismiss' if english else '收起')
        self.style_button.setToolTip(('Current: ' if english else '当前：') + character)
        self.health_button.setToolTip('Open the private health & food assistant' if english else '打开本地配置的健康饮食助手')
        self.key_hint.setToolTip('Scroll or ← / →' if english else '滚轮或 ← / → 切换表情')
        for emotion_id, button in self.buttons.items():
            selected = emotion_id == state['emotion']
            if button.property('selected') != selected or restyle:
                button.setProperty('selected', selected)
                button.setIcon(self.icons[emotion_id][1 if selected else 0])
                button.style().unpolish(button)
                button.style().polish(button)
                button.update()
        if select_group:
            self.select_group(current['group'])

    def select_group(self, group):
        self.group = group
        self.tabs[group].setChecked(True)
        while self.grid.count():
            self.grid.takeAt(0).widget().hide()
        choices = [e for e in self.emotions if e['group'] == group]
        for index, emotion in enumerate(choices):
            button = self.buttons[emotion['id']]
            self.grid.addWidget(button, index // 3, index % 3)
            button.show()
        rows = ceil(len(choices) / 3)
        self.grid_host.setFixedHeight(rows * 29 + (rows - 1) * 3 + 4)
        self.adjustSize()
        if self.isVisible():
            self.clamp_position()

    def pick(self, emotion_id):
        self.pet.change_state(emotion=emotion_id)

    def switch_style(self):
        character = 'pink-robot' if self.pet.state['character'] == 'robot' else 'robot'
        self.pet.change_state(character=character)

    def open_health(self):
        self.hide()
        self.pet.open_health_assistant()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        for spread in range(5, 0, -1):
            painter.setBrush(QColor(0, 0, 0, 3 + 2 * (5 - spread)))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(6 - spread, 6 - spread + 1, -6 + spread, -6 + spread + 1), 10 + spread, 10 + spread)
        painter.setPen(QPen(self.panel_border, 1))
        painter.setBrush(self.panel_surface)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(5.5, 5.5, -5.5, -5.5), 10, 10)

    def step(self, delta):
        self.pet.cycle_emotion(delta)
        self.sync_state(select_group=True)

    def clamp_position(self):
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(max(area.left(), min(self.x(), area.right() - self.width() + 1)),
                  max(area.top(), min(self.y(), area.bottom() - self.height() + 1)))

    def popup(self, position=None):
        self.sync_state(select_group=True)
        self.adjustSize()
        anchor = position or QCursor.pos()
        screen = QApplication.screenAt(anchor) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        x = anchor.x() + 6 if anchor.x() + self.width() + 6 <= area.right() else anchor.x() - self.width() - 6
        y = anchor.y() + 6 if anchor.y() + self.height() + 6 <= area.bottom() else anchor.y() - self.height() - 6
        self.move(max(area.left(), min(x, area.right() - self.width() + 1)), max(area.top(), min(y, area.bottom() - self.height() + 1)))
        self.show()
        self.raise_()
        self.setFocus(Qt.PopupFocusReason)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
        elif event.key() in (Qt.Key_Left, Qt.Key_Right):
            self.step(-1 if event.key() == Qt.Key_Left else 1)
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        if event.angleDelta().y():
            self.step(-1 if event.angleDelta().y() > 0 else 1)
        event.accept()
