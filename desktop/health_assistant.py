"""Native health assistant window for the Windows desktop pet."""
import html
import threading

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QShortcut,
    QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from desktop.health_api import (
    DEFAULT_ENDPOINTS, DEFAULT_MODELS, HealthApiError, HealthSettingsStore, perform_chat,
    sync_native_skill, urgent_notice,
)


PROTOCOL_LABELS = (
    ('OpenAI Responses + native Skill', 'openai_responses'),
    ('OpenAI-compatible', 'openai'),
    ('DeepSeek (official)', 'deepseek'),
    ('Anthropic Messages', 'anthropic'),
    ('Google Gemini', 'gemini'),
    ('Ollama (local)', 'ollama'),
)


class PromptEdit(QTextEdit):
    submitRequested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() & Qt.ControlModifier:
            self.submitRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class WorkerSignals(QObject):
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)
    finished = pyqtSignal()


class ChatWorker:
    """Daemon-backed request worker so an in-flight API call never blocks app exit."""

    def __init__(self, config, history, prompt, parent=None):
        self.signals = WorkerSignals(parent)
        self.config = config
        self.history = history
        self.prompt = prompt
        self.thread = threading.Thread(target=self.run, name='little-p-health-api', daemon=True)

    def start(self):
        self.thread.start()

    def isRunning(self):
        return self.thread.is_alive()

    def run(self):
        try:
            self.signals.completed.emit(perform_chat(self.config, self.history, self.prompt))
        except Exception as error:
            message = str(error) if isinstance(error, HealthApiError) else '请求模型时发生未知错误。'
            try:
                self.signals.failed.emit(message)
            except RuntimeError:
                pass
        finally:
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


class SkillSyncWorker:
    def __init__(self, config, parent=None):
        self.signals = WorkerSignals(parent)
        self.config = config
        self.thread = threading.Thread(target=self.run, name='little-p-skill-sync', daemon=True)

    def start(self):
        self.thread.start()

    def isRunning(self):
        return self.thread.is_alive()

    def run(self):
        try:
            self.signals.completed.emit(sync_native_skill(self.config))
        except Exception as error:
            message = str(error) if isinstance(error, HealthApiError) else '同步 Skill 时发生未知错误。'
            try:
                self.signals.failed.emit(message)
            except RuntimeError:
                pass
        finally:
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


class HealthAssistantDialog(QDialog):
    def __init__(self, pet):
        super().__init__(pet, Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)
        self.pet = pet
        self.store = HealthSettingsStore()
        self.history = []
        self.worker = None
        self.last_answer = ''
        self.english = False
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setMinimumSize(620, 590)
        self.resize(720, 700)
        self._build_ui()
        self._load_settings()
        self.sync_state()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(13)

        heading = QHBoxLayout()
        heading.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title = QLabel(self)
        self.title.setObjectName('assistantTitle')
        self.subtitle = QLabel(self)
        self.subtitle.setObjectName('assistantSubtitle')
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        heading.addLayout(titles)
        heading.addStretch()
        self.local_badge = QLabel(self)
        self.local_badge.setObjectName('localBadge')
        heading.addWidget(self.local_badge)
        root.addLayout(heading)

        self.tabs = QTabWidget(self)
        self.chat_tab = QWidget(self.tabs)
        self.settings_tab = QWidget(self.tabs)
        self.tabs.addTab(self.chat_tab, '')
        self.tabs.addTab(self.settings_tab, '')
        root.addWidget(self.tabs, 1)
        self._build_chat_tab()
        self._build_settings_tab()

        self.status = QLabel(self)
        self.status.setObjectName('status')
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        QShortcut(QKeySequence('Ctrl+L'), self, activated=self.clear_chat)

    def _build_chat_tab(self):
        layout = QVBoxLayout(self.chat_tab)
        layout.setContentsMargins(13, 14, 13, 12)
        layout.setSpacing(10)
        self.safety_note = QLabel(self.chat_tab)
        self.safety_note.setObjectName('safetyNote')
        self.safety_note.setWordWrap(True)
        layout.addWidget(self.safety_note)
        self.transcript = QTextBrowser(self.chat_tab)
        self.transcript.setObjectName('transcript')
        self.transcript.setOpenExternalLinks(False)
        layout.addWidget(self.transcript, 1)

        quick = QHBoxLayout()
        quick.setSpacing(7)
        self.quick_buttons = []
        for index in range(3):
            button = QPushButton(self.chat_tab)
            button.setProperty('role', 'quick')
            button.clicked.connect(lambda checked=False, i=index: self.use_quick_prompt(i))
            quick.addWidget(button)
            self.quick_buttons.append(button)
        layout.addLayout(quick)

        self.prompt = PromptEdit(self.chat_tab)
        self.prompt.setObjectName('prompt')
        self.prompt.setAcceptRichText(False)
        self.prompt.setFixedHeight(92)
        self.prompt.submitRequested.connect(self.send_prompt)
        layout.addWidget(self.prompt)
        actions = QHBoxLayout()
        self.input_hint = QLabel(self.chat_tab)
        self.input_hint.setObjectName('inputHint')
        actions.addWidget(self.input_hint)
        actions.addStretch()
        self.clear_button = QPushButton(self.chat_tab)
        self.clear_button.clicked.connect(self.clear_chat)
        self.copy_button = QPushButton(self.chat_tab)
        self.copy_button.clicked.connect(self.copy_answer)
        self.send_button = QPushButton(self.chat_tab)
        self.send_button.setObjectName('primaryButton')
        self.send_button.clicked.connect(self.send_prompt)
        actions.addWidget(self.clear_button)
        actions.addWidget(self.copy_button)
        actions.addWidget(self.send_button)
        layout.addLayout(actions)

    def _build_settings_tab(self):
        layout = QVBoxLayout(self.settings_tab)
        layout.setContentsMargins(18, 20, 18, 16)
        layout.setSpacing(13)
        self.settings_intro = QLabel(self.settings_tab)
        self.settings_intro.setWordWrap(True)
        layout.addWidget(self.settings_intro)
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(11)
        self.protocol = QComboBox(self.settings_tab)
        for label, value in PROTOCOL_LABELS:
            self.protocol.addItem(label, value)
        self.protocol.currentIndexChanged.connect(self.protocol_changed)
        self.endpoint = QLineEdit(self.settings_tab)
        self.model = QLineEdit(self.settings_tab)
        self.api_key = QLineEdit(self.settings_tab)
        self.api_key.setEchoMode(QLineEdit.Password)
        self.show_key = QCheckBox(self.settings_tab)
        self.show_key.toggled.connect(lambda shown: self.api_key.setEchoMode(QLineEdit.Normal if shown else QLineEdit.Password))
        key_row = QHBoxLayout()
        key_row.setContentsMargins(0, 0, 0, 0)
        key_row.addWidget(self.api_key, 1)
        key_row.addWidget(self.show_key)
        key_host = QWidget(self.settings_tab)
        key_host.setLayout(key_row)
        self.temperature = QDoubleSpinBox(self.settings_tab)
        self.temperature.setRange(0, 2)
        self.temperature.setSingleStep(.1)
        self.temperature.setDecimals(1)
        self.temperature.setValue(.3)
        self.protocol_label = QLabel(self.settings_tab)
        self.endpoint_label = QLabel(self.settings_tab)
        self.model_label = QLabel(self.settings_tab)
        self.key_label = QLabel(self.settings_tab)
        self.temperature_label = QLabel(self.settings_tab)
        form.addRow(self.protocol_label, self.protocol)
        form.addRow(self.endpoint_label, self.endpoint)
        form.addRow(self.model_label, self.model)
        form.addRow(self.key_label, key_host)
        form.addRow(self.temperature_label, self.temperature)
        layout.addLayout(form)
        self.skill_note = QLabel(self.settings_tab)
        self.skill_note.setObjectName('skillNote')
        self.skill_note.setWordWrap(True)
        layout.addWidget(self.skill_note)
        self.privacy_note = QLabel(self.settings_tab)
        self.privacy_note.setObjectName('privacyNote')
        self.privacy_note.setWordWrap(True)
        layout.addWidget(self.privacy_note)
        layout.addStretch()
        buttons = QHBoxLayout()
        self.clear_key_button = QPushButton(self.settings_tab)
        self.clear_key_button.clicked.connect(self.clear_saved_key)
        self.sync_skill_button = QPushButton(self.settings_tab)
        self.sync_skill_button.clicked.connect(self.sync_skill)
        self.test_button = QPushButton(self.settings_tab)
        self.test_button.clicked.connect(self.test_connection)
        self.save_button = QPushButton(self.settings_tab)
        self.save_button.setObjectName('primaryButton')
        self.save_button.clicked.connect(self.save_settings)
        buttons.addWidget(self.clear_key_button)
        buttons.addWidget(self.sync_skill_button)
        buttons.addStretch()
        buttons.addWidget(self.test_button)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)

    def sync_state(self):
        self.english = self.pet.state.get('lang') == 'en'
        self._translate()
        self._apply_theme(self.pet.state.get('theme') == 'dark')

    def _translate(self):
        en = self.english
        self.setWindowTitle('Little P · Health Assistant' if en else 'Little P · 健康饮食助手')
        self.title.setText('Health & food assistant' if en else '健康饮食助手')
        self.subtitle.setText('Practical food guidance powered by your model' if en else '用你自己的模型，获得可执行的饮食建议')
        self.local_badge.setText('LOCAL KEY' if en else '密钥仅存本机')
        self.tabs.setTabText(0, 'Chat' if en else '对话')
        self.tabs.setTabText(1, 'Model API' if en else '模型 API')
        self.safety_note.setText(
            'General education only—not diagnosis or emergency care. Your message is sent only to the API you configure.' if en else
            '用于一般健康教育，不替代诊断、治疗或急救。你的消息只会发送到你配置的模型接口。'
        )
        quick_en = ('Review today’s meals', 'Suggest my next meal', 'Healthier takeout')
        quick_zh = ('复盘今天吃的', '建议我的下一餐', '外食怎么选')
        for button, label in zip(self.quick_buttons, quick_en if en else quick_zh):
            button.setText(label)
        self.prompt.setPlaceholderText('Describe what you ate, your goal, allergies, or restrictions…' if en else '说说你吃了什么、想改善什么，以及过敏或忌口…')
        self.input_hint.setText('Ctrl+Enter to send · conversation is not saved' if en else 'Ctrl+Enter 发送 · 对话不会保存')
        self.clear_button.setText('Clear' if en else '清空')
        self.copy_button.setText('Copy answer' if en else '复制回答')
        self.send_button.setText('Send' if en else '发送')
        self.settings_intro.setText(
            'Use OpenAI Responses for the bundled native Skill, or choose DeepSeek and other compatible providers directly.' if en else
            '使用 OpenAI Responses 可挂载内置原生 Skill；DeepSeek 等其他服务可直接选择对应入口。'
        )
        self.protocol_label.setText('API format' if en else 'API 格式')
        self.endpoint_label.setText('Endpoint' if en else '接口地址')
        self.model_label.setText('Model' if en else '模型名称')
        self.key_label.setText('API Key' if en else 'API Key')
        self.temperature_label.setText('Temperature' if en else '回答温度')
        self.show_key.setText('Show' if en else '显示')
        self.api_key.setPlaceholderText('Saved securely; leave blank to keep it' if en else '已安全保存时留空即可保留')
        self.privacy_note.setText(
            'The key is encrypted with Windows DPAPI for this user and stored under LocalAppData. It is never put into the web page, repository, logs, or chat history. Prompts are subject to your API provider’s privacy policy.' if en else
            'API Key 使用 Windows DPAPI 绑定当前用户加密，并保存在 LocalAppData。它不会进入网页、仓库、日志或对话记录；发送内容仍受你所选 API 服务商的隐私政策约束。'
        )
        self.clear_key_button.setText('Remove saved key' if en else '删除本地 Key')
        self.sync_skill_button.setText('Sync built-in Skill' if en else '同步内置 Skill')
        self.test_button.setText('Save & test' if en else '保存并测试')
        self.save_button.setText('Save settings' if en else '保存配置')
        if not self.history:
            self._welcome()

    def _apply_theme(self, dark):
        colors = {
            'bg': '#202220' if dark else '#f7f6f2', 'surface': '#292c29' if dark else '#ffffff',
            'text': '#f0efe9' if dark else '#2d302c', 'muted': '#a6aaa1' if dark else '#747a71',
            'line': '#41453f' if dark else '#dddeda', 'soft': '#323630' if dark else '#f0f2ed',
            'accent': '#9fd0bd' if dark else '#356c59', 'accent_bg': '#1f4638' if dark else '#dcefe7',
            'warn': '#f0d5a0' if dark else '#75531b', 'warn_bg': '#463a24' if dark else '#fff5dc',
        }
        self.setStyleSheet('''
            QDialog {background:%(bg)s;color:%(text)s;font:13px "Microsoft YaHei"}
            QLabel {color:%(text)s}
            QLabel#assistantTitle {font-size:24px;font-weight:650}
            QLabel#assistantSubtitle,QLabel#inputHint,QLabel#status {color:%(muted)s;font-size:11px}
            QLabel#localBadge {padding:5px 9px;border-radius:10px;background:%(accent_bg)s;color:%(accent)s;font-size:10px;font-weight:650}
            QLabel#safetyNote,QLabel#privacyNote,QLabel#skillNote {padding:10px 12px;border:1px solid %(line)s;border-radius:7px;background:%(soft)s;color:%(muted)s}
            QTabWidget::pane {border:1px solid %(line)s;border-radius:9px;background:%(surface)s}
            QTabBar::tab {padding:9px 18px;color:%(muted)s;background:transparent}
            QTabBar::tab:selected {color:%(text)s;border-bottom:2px solid %(accent)s}
            QTextBrowser,QTextEdit,QLineEdit,QComboBox,QDoubleSpinBox {border:1px solid %(line)s;border-radius:6px;background:%(bg)s;color:%(text)s;padding:7px;selection-background-color:%(accent)s}
            QTextBrowser {padding:10px}
            QPushButton {min-height:32px;padding:0 12px;border:1px solid %(line)s;border-radius:6px;background:%(surface)s;color:%(text)s}
            QPushButton:hover {background:%(soft)s}
            QPushButton:disabled {color:%(muted)s}
            QPushButton#primaryButton {border-color:%(accent)s;background:%(accent)s;color:white;font-weight:600}
            QPushButton[role="quick"] {min-height:30px;padding:0 9px;color:%(accent)s;background:%(accent_bg)s;border-color:%(accent_bg)s}
            QCheckBox {color:%(muted)s}
        ''' % colors)

    def _welcome(self):
        self.transcript.clear()
        text = (
            'Tell me what you ate or what you want to improve. I’ll ask only for information needed for a safer suggestion.' if self.english else
            '告诉我你吃了什么，或想改善什么。我会先补充必要信息，再给出温和、能执行的饮食建议。'
        )
        self._append_message('assistant', text)

    def _append_message(self, role, text, warning=False):
        safe = html.escape(str(text)).replace('\n', '<br>')
        if warning:
            label = 'Safety notice' if self.english else '安全提示'
            color = '#a85c00'
        elif role == 'user':
            label = 'You' if self.english else '你'
            color = '#356c59'
        else:
            label = 'Little P'
            color = '#6b577c'
        self.transcript.append(
            f'<div style="margin:8px 0 3px;color:{color};font-weight:600">{label}</div>'
            f'<div style="margin:0 0 11px;line-height:1.55">{safe}</div>'
        )
        self.transcript.verticalScrollBar().setValue(self.transcript.verticalScrollBar().maximum())

    def use_quick_prompt(self, index):
        prompts_en = (
            'Please help me review what I ate today. Ask me for the minimum information you need.',
            'Please suggest my next meal. Ask about allergies, restrictions, and what I already ate if needed.',
            'I am eating out. Help me choose a more balanced meal and ask what options are available.',
        )
        prompts_zh = (
            '请帮我复盘今天的饮食，并先问我你真正需要的信息。',
            '请建议我的下一餐；如有必要，先问过敏、忌口和今天已经吃了什么。',
            '我准备外食，请帮我选一顿更均衡的餐，并先问有哪些选择。',
        )
        self.prompt.setPlainText((prompts_en if self.english else prompts_zh)[index])
        self.prompt.setFocus()

    def _load_settings(self):
        config = self.store.load()
        index = self.protocol.findData(config['protocol'])
        self.protocol.setCurrentIndex(max(0, index))
        self.endpoint.setText(config['endpoint'])
        self.model.setText(config['model'])
        self.temperature.setValue(float(config['temperature']))
        self.api_key.clear()
        self.api_key.setProperty('stored', config['has_api_key'])
        self._update_skill_ui(config)
        if not config['configured']:
            self.tabs.setCurrentWidget(self.settings_tab)

    def protocol_changed(self):
        selected = self.protocol.currentData()
        current = self.endpoint.text().strip()
        current_model = self.model.text().strip()
        if not current or current in DEFAULT_ENDPOINTS.values():
            self.endpoint.setText(DEFAULT_ENDPOINTS[selected])
        if selected in DEFAULT_MODELS and (not current_model or current_model in DEFAULT_MODELS.values()):
            self.model.setText(DEFAULT_MODELS[selected])
        self._update_skill_ui(self.store.load())

    def _update_skill_ui(self, config=None):
        native = self.protocol.currentData() == 'openai_responses'
        config = config or {}
        synced = bool(config.get('skill_id'))
        self.skill_note.setVisible(native)
        self.sync_skill_button.setVisible(native)
        if not native:
            return
        if synced:
            text = 'Built-in Skill is synced. It will be versioned again when its content changes.' if self.english else '内置 Skill 已同步；内容更新后可再次同步为新版本。'
        else:
            text = 'Not synced. Clicking Sync uploads only the bundled SKILL.md to the official OpenAI API.' if self.english else '尚未同步。点击后只会把内置 SKILL.md 上传到 OpenAI 官方 API。'
        self.skill_note.setText(text)

    def _form_values(self):
        return {
            'protocol': self.protocol.currentData(), 'endpoint': self.endpoint.text().strip(),
            'model': self.model.text().strip(), 'temperature': self.temperature.value(),
        }

    def save_settings(self, quiet=False):
        key = self.api_key.text()
        try:
            saved = self.store.save(self._form_values(), api_key=key if key else None)
        except (HealthApiError, OSError) as error:
            if not quiet:
                QMessageBox.warning(self, self.windowTitle(), str(error))
            return None
        self.api_key.clear()
        self.api_key.setProperty('stored', saved['has_api_key'])
        self._update_skill_ui(self.store.load())
        self._set_status('Saved locally.' if self.english else '配置已保存在本机。', False)
        return saved

    def sync_skill(self):
        if self.worker and self.worker.isRunning():
            return
        if self.protocol.currentData() != 'openai_responses':
            return
        if not self.save_settings(quiet=True):
            QMessageBox.warning(self, self.windowTitle(), 'Please complete the API settings first.' if self.english else '请先完整填写并保存 API 配置。')
            return
        question = (
            'Upload Little P’s bundled SKILL.md to the official OpenAI API? The file contains recommendation instructions and no conversation or API key.' if self.english else
            '是否把 Little P 内置的 SKILL.md 上传到 OpenAI 官方 API？该文件只包含推荐规则，不包含对话内容或 API Key。'
        )
        if QMessageBox.question(self, self.windowTitle(), question) != QMessageBox.Yes:
            return
        self._set_busy(True, skill=True)
        worker = SkillSyncWorker(self._request_config(), self)
        worker.signals.completed.connect(self._skill_sync_done)
        worker.signals.failed.connect(self._skill_sync_failed)
        self.worker = worker
        worker.start()

    def _skill_sync_done(self, skill_id):
        self._set_busy(False)
        self.worker = None
        self._update_skill_ui(self.store.load())
        self._set_status(('Skill synced: ' if self.english else 'Skill 同步成功：') + skill_id, False)

    def _skill_sync_failed(self, error):
        self._set_busy(False)
        self.worker = None
        self._set_status(error, True)

    def clear_saved_key(self):
        self.store.clear_key()
        self.api_key.clear()
        self.api_key.setProperty('stored', False)
        self._set_status('Saved key removed.' if self.english else '已删除本地保存的 API Key。', False)

    def _request_config(self):
        config = self.store.load()
        config['_store'] = self.store
        return config

    def send_prompt(self):
        if self.worker and self.worker.isRunning():
            return
        text = self.prompt.toPlainText().strip()
        if not text:
            return
        config = self.store.load()
        if not config['configured']:
            self.tabs.setCurrentWidget(self.settings_tab)
            self._set_status('Configure a model API first.' if self.english else '请先配置模型 API。', True)
            return
        warning = urgent_notice(text, self.english)
        if warning:
            self._append_message('assistant', warning, warning=True)
        self._append_message('user', text)
        self.prompt.clear()
        self._start_worker(self._request_config(), list(self.history), text, test=False)

    def test_connection(self):
        if self.worker and self.worker.isRunning():
            return
        if not self.save_settings():
            return
        prompt = 'Reply with only: Connection successful' if self.english else '请只回复：连接成功'
        self._start_worker(self._request_config(), [], prompt, test=True)

    def _start_worker(self, config, history, prompt, test):
        self._set_busy(True, test)
        worker = ChatWorker(config, history, prompt, self)
        worker.signals.completed.connect(lambda answer, p=prompt, t=test: self._request_done(answer, p, t))
        worker.signals.failed.connect(lambda error, t=test: self._request_failed(error, t))
        self.worker = worker
        worker.start()

    def _request_done(self, answer, prompt, test):
        self._set_busy(False, test)
        self.worker = None
        if test:
            self._set_status(('Connection works: ' if self.english else '连接成功：') + answer[:120], False)
            self.tabs.setCurrentWidget(self.chat_tab)
            return
        self.history.extend(({'role': 'user', 'content': prompt}, {'role': 'assistant', 'content': answer}))
        self.history = self.history[-12:]
        self.last_answer = answer
        self._append_message('assistant', answer)
        self._set_status('Answer received.' if self.english else '回答完成。', False)

    def _request_failed(self, error, test):
        self._set_busy(False, test)
        self.worker = None
        self._set_status(error, True)
        if not test:
            self._append_message('assistant', ('Request failed: ' if self.english else '请求失败：') + error, warning=True)

    def _set_busy(self, busy, test=False, skill=False):
        self.send_button.setDisabled(busy)
        self.test_button.setDisabled(busy)
        self.save_button.setDisabled(busy)
        self.sync_skill_button.setDisabled(busy)
        if busy:
            self._set_status(
                'Syncing Skill…' if skill and self.english else '正在同步 Skill…' if skill else
                'Testing…' if test and self.english else '正在测试…' if test else
                'Thinking…' if self.english else '正在生成建议…', False
            )

    def _set_status(self, text, error=False):
        self.status.setText(text)
        self.status.setStyleSheet('color:#bd4f55' if error else '')

    def clear_chat(self):
        if self.worker and self.worker.isRunning():
            return
        self.history = []
        self.last_answer = ''
        self._welcome()
        self._set_status('Conversation cleared.' if self.english else '当前对话已清空。', False)

    def copy_answer(self):
        if self.last_answer:
            QApplication.clipboard().setText(self.last_answer)
            self._set_status('Copied.' if self.english else '已复制最近一条回答。', False)

    def showEvent(self, event):
        self.sync_state()
        self._load_settings()
        super().showEvent(event)

    def closeEvent(self, event):
        self.hide()
        event.ignore()
