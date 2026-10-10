"""Provider-neutral chat transport and local secret storage for the health assistant."""
import base64
import ctypes
from ctypes import wintypes
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
import zipfile
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from runtime_paths import data_root, resource_root


ROOT = resource_root()
CONFIG_PATH = data_root() / 'health-assistant.json'
SYSTEM_PROMPT_PATH = ROOT / 'desktop' / 'health_system.md'
SKILL_PATH = ROOT / 'desktop' / 'health_skill' / 'SKILL.md'
LEGACY_SKILL_PATH = ROOT / 'desktop' / 'health_skill.md'
MAX_INPUT_CHARS = 4000
MAX_HISTORY_MESSAGES = 12
MAX_HISTORY_CHARS = 24000
PROTOCOLS = ('openai_responses', 'openai', 'deepseek', 'anthropic', 'gemini', 'ollama')
DEFAULT_ENDPOINTS = {
    'openai_responses': 'https://api.openai.com/v1/responses',
    'openai': 'https://api.openai.com/v1/chat/completions',
    'deepseek': 'https://api.deepseek.com/chat/completions',
    'anthropic': 'https://api.anthropic.com/v1/messages',
    'gemini': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
    'ollama': 'http://127.0.0.1:11434/api/chat',
}
DEFAULT_MODELS = {
    'deepseek': 'deepseek-flash',
}
DEFAULT_CONFIG = {
    'protocol': 'openai_responses',
    'endpoint': DEFAULT_ENDPOINTS['openai_responses'],
    'model': '',
    'temperature': 0.3,
}
SKILL_METADATA_KEYS = ('skill_id', 'skill_digest')


class HealthApiError(RuntimeError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]


def _blob_from_bytes(value):
    buffer = ctypes.create_string_buffer(value)
    return _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def protect_secret(value):
    """Encrypt a secret for the current Windows user with DPAPI."""
    if not value:
        return ''
    if os.name != 'nt':
        raise HealthApiError('API Key 加密仅支持 Windows。')
    source, source_buffer = _blob_from_bytes(value.encode('utf-8'))
    target = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob), wintypes.LPCWSTR, ctypes.POINTER(_DataBlob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    if not crypt32.CryptProtectData(ctypes.byref(source), 'Little P health assistant API key', None, None, None, 0x1, ctypes.byref(target)):
        raise HealthApiError('无法使用 Windows 账户加密 API Key。')
    try:
        encrypted = ctypes.string_at(target.pbData, target.cbData)
        return base64.b64encode(encrypted).decode('ascii')
    finally:
        kernel32.LocalFree(ctypes.cast(target.pbData, ctypes.c_void_p))
        del source_buffer


def unprotect_secret(value):
    if not value:
        return ''
    if os.name != 'nt':
        raise HealthApiError('API Key 解密仅支持 Windows。')
    try:
        encrypted = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise HealthApiError('本地 API Key 数据已损坏，请重新保存。') from error
    source, source_buffer = _blob_from_bytes(encrypted)
    target = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(_DataBlob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    if not crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0x1, ctypes.byref(target)):
        raise HealthApiError('无法解密 API Key；请使用保存它的 Windows 账户。')
    try:
        return ctypes.string_at(target.pbData, target.cbData).decode('utf-8')
    finally:
        kernel32.LocalFree(ctypes.cast(target.pbData, ctypes.c_void_p))
        del source_buffer


def validate_config(value):
    if not isinstance(value, dict):
        raise HealthApiError('API 配置格式不正确。')
    protocol = str(value.get('protocol', '')).strip().lower()
    if protocol not in PROTOCOLS:
        raise HealthApiError('请选择支持的 API 格式。')
    endpoint = str(value.get('endpoint', '')).strip()
    model = str(value.get('model', '')).strip()
    if not endpoint or len(endpoint) > 2048:
        raise HealthApiError('请填写有效的接口地址。')
    if not model or len(model) > 160 or any(char in model for char in '\r\n'):
        raise HealthApiError('请填写有效的模型名称。')
    expanded_endpoint = endpoint.replace('{model}', quote(model, safe='-._~'))
    parsed = urlsplit(expanded_endpoint)
    local_hosts = {'127.0.0.1', 'localhost', '::1'}
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise HealthApiError('接口地址必须是完整的 HTTP(S) URL。')
    if parsed.scheme != 'https' and parsed.hostname.lower() not in local_hosts:
        raise HealthApiError('远程接口必须使用 HTTPS；HTTP 仅允许本机地址。')
    secret_query_names = {'key', 'api_key', 'apikey', 'token', 'access_token', 'authorization'}
    if any(name.lower() in secret_query_names for name, _ in parse_qsl(parsed.query, keep_blank_values=True)):
        raise HealthApiError('请把密钥填写在 API Key 输入框，不要放在接口地址中。')
    try:
        temperature = float(value.get('temperature', 0.3))
    except (TypeError, ValueError) as error:
        raise HealthApiError('温度参数不正确。') from error
    if not 0 <= temperature <= 2:
        raise HealthApiError('温度参数必须在 0 到 2 之间。')
    return dict(protocol=protocol, endpoint=endpoint, model=model, temperature=temperature)


class HealthSettingsStore:
    def __init__(self, path=CONFIG_PATH):
        self.path = Path(path)

    def _read_raw(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            return {}

    def load(self, reveal_key=False):
        raw = self._read_raw()
        values = dict(DEFAULT_CONFIG)
        values.update({key: raw[key] for key in DEFAULT_CONFIG if key in raw})
        values.update({key: raw[key] for key in SKILL_METADATA_KEYS if key in raw})
        values['configured'] = bool(values.get('model') and values.get('endpoint'))
        values['has_api_key'] = bool(raw.get('api_key_dpapi'))
        values['api_key'] = ''
        if reveal_key and raw.get('api_key_dpapi'):
            values['api_key'] = unprotect_secret(raw['api_key_dpapi'])
        return values

    def save(self, values, api_key=None, clear_key=False):
        clean = validate_config(values)
        raw = self._read_raw()
        saved = dict(clean)
        if raw.get('protocol') == clean['protocol'] and raw.get('endpoint') == clean['endpoint']:
            saved.update({key: raw[key] for key in SKILL_METADATA_KEYS if key in raw})
        if clear_key:
            saved['api_key_dpapi'] = ''
        elif api_key is not None:
            saved['api_key_dpapi'] = protect_secret(api_key.strip()) if api_key.strip() else ''
        else:
            saved['api_key_dpapi'] = raw.get('api_key_dpapi', '')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='health-', suffix='.tmp', dir=str(self.path.parent))
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
                json.dump(saved, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
        result = dict(clean)
        result['configured'] = True
        result['has_api_key'] = bool(saved.get('api_key_dpapi'))
        result['api_key'] = ''
        return result

    def save_skill_reference(self, skill_id, skill_digest):
        raw = self._read_raw()
        raw['skill_id'] = str(skill_id)
        raw['skill_digest'] = str(skill_digest)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix='health-', suffix='.tmp', dir=str(self.path.parent))
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
                json.dump(raw, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def clear_key(self):
        raw = self._read_raw()
        if raw:
            raw['api_key_dpapi'] = ''
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _read_required(path, label):
    try:
        value = path.read_text(encoding='utf-8').strip()
    except OSError as error:
        raise HealthApiError(f'健康助手 {label} 文件缺失，请重新安装 Little P。') from error
    if not value:
        raise HealthApiError(f'健康助手 {label} 文件为空，请重新安装 Little P。')
    return value


def load_skill():
    if SKILL_PATH.exists():
        return _read_required(SKILL_PATH, 'Skill')
    return _read_required(LEGACY_SKILL_PATH, 'Skill')


def _skill_body(value):
    if value.startswith('---'):
        parts = value.split('---', 2)
        if len(parts) == 3:
            return parts[2].strip()
    return value


def load_system_prompt(include_skill=True):
    if SYSTEM_PROMPT_PATH.exists():
        system_prompt = _read_required(SYSTEM_PROMPT_PATH, '安全规则')
    else:
        system_prompt = _skill_body(load_skill())
    if include_skill:
        workflow = _skill_body(load_skill())
        if workflow not in system_prompt:
            system_prompt += '\n\n# 推荐工作流\n\n' + workflow
    return system_prompt


def trim_history(history):
    cleaned = []
    total = 0
    for item in reversed(list(history or [])):
        if not isinstance(item, dict) or item.get('role') not in ('user', 'assistant'):
            continue
        content = str(item.get('content', '')).strip()
        if not content:
            continue
        content = content[:MAX_INPUT_CHARS]
        if cleaned and total + len(content) > MAX_HISTORY_CHARS:
            break
        cleaned.append({'role': item['role'], 'content': content})
        total += len(content)
        if len(cleaned) >= MAX_HISTORY_MESSAGES:
            break
    return list(reversed(cleaned))


def _skill_upload_url(responses_endpoint, skill_id=''):
    parsed = urlsplit(responses_endpoint)
    if parsed.scheme != 'https' or parsed.hostname != 'api.openai.com' or parsed.port not in (None, 443):
        raise HealthApiError('原生 Skill 仅允许同步到 OpenAI 官方 api.openai.com。第三方接口请使用兼容模式。')
    path = parsed.path.rstrip('/')
    if path != '/v1/responses':
        raise HealthApiError('原生 Skill 模式的接口地址必须是 https://api.openai.com/v1/responses。')
    path = '/v1/skills'
    if skill_id:
        path += '/' + quote(str(skill_id), safe='-_') + '/versions'
    return urlunsplit(('https', 'api.openai.com', path, '', ''))


def _skill_bundle(skill_text):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('littlep-health/SKILL.md', skill_text.encode('utf-8'))
    return buffer.getvalue()


def _multipart_file(field, filename, content, content_type):
    boundary = '----LittleP' + uuid.uuid4().hex
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f'Content-Type: {content_type}\r\n\r\n'
    ).encode('ascii') + content + f'\r\n--{boundary}--\r\n'.encode('ascii')
    return body, 'multipart/form-data; boundary=' + boundary


def sync_native_skill(config, timeout=60, opener=urlopen):
    """Upload/version the bundled Skill after an explicit user action."""
    effective = dict(config)
    if effective.get('protocol') != 'openai_responses':
        raise HealthApiError('请先选择 OpenAI Responses + 原生 Skill。')
    clean = validate_config(effective)
    api_key = str(effective.get('api_key', '') or '').strip()
    if not api_key:
        raise HealthApiError('同步原生 Skill 需要 API Key。')
    skill_text = load_skill()
    digest = hashlib.sha256(skill_text.encode('utf-8')).hexdigest()
    skill_id = str(effective.get('skill_id', '') or '').strip()
    if skill_id and effective.get('skill_digest') == digest:
        return skill_id

    endpoint = _skill_upload_url(clean['endpoint'], skill_id)
    body, content_type = _multipart_file('files', 'littlep-health.zip', _skill_bundle(skill_text), 'application/zip')
    request = Request(endpoint, data=body, headers={
        'Authorization': 'Bearer ' + api_key,
        'Accept': 'application/json',
        'Content-Type': content_type,
    }, method='POST')
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        detail = _safe_error_body(error.read()).replace(api_key, '••••')
        message = f'Skill 同步失败（HTTP {error.code}）' + (f'：{detail}' if detail else '。')
        raise HealthApiError(message) from error
    except URLError as error:
        raise HealthApiError(f'无法同步 Skill：{str(error.reason)[:240]}') from error
    except (OSError, ValueError) as error:
        raise HealthApiError('Skill 同步响应无法读取。') from error

    if not skill_id:
        skill_id = str(payload.get('id', '') or '').strip()
    if not skill_id:
        raise HealthApiError('Skill 已上传，但接口没有返回 skill_id。')
    store = effective.get('_store')
    if store:
        store.save_skill_reference(skill_id, digest)
    return skill_id


def build_request(config, history, prompt, system_prompt=None):
    clean = validate_config(config)
    prompt = str(prompt or '').strip()
    if not prompt:
        raise HealthApiError('请先输入饮食或健康问题。')
    if len(prompt) > MAX_INPUT_CHARS:
        raise HealthApiError(f'单次输入请控制在 {MAX_INPUT_CHARS} 字以内。')
    protocol = clean['protocol']
    native_skill = protocol == 'openai_responses'
    system_prompt = system_prompt or load_system_prompt(include_skill=not native_skill)
    messages = trim_history(history) + [{'role': 'user', 'content': prompt}]
    endpoint = clean['endpoint'].replace('{model}', quote(clean['model'], safe='-._~'))
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    api_key = str(config.get('api_key', '') or '').strip()
    if protocol == 'openai_responses':
        if api_key:
            headers['Authorization'] = 'Bearer ' + api_key
        skill_id = str(config.get('skill_id', '') or '').strip()
        if not skill_id:
            raise HealthApiError('内置 Skill 尚未同步，请在“模型 API”页点击“同步内置 Skill”。')
        body = {
            'model': clean['model'],
            'instructions': system_prompt + '\n\n对饮食与健康请求，请使用 littlep-health-recommendation Skill 的工作流。',
            'input': messages,
            'tools': [{
                'type': 'shell',
                'environment': {
                    'type': 'container_auto',
                    'skills': [{'type': 'skill_reference', 'skill_id': skill_id, 'version': 'latest'}],
                },
            }],
            'tool_choice': 'auto',
            'temperature': clean['temperature'],
            'max_output_tokens': 900,
            'store': False,
        }
    elif protocol in ('openai', 'deepseek'):
        if api_key:
            headers['Authorization'] = 'Bearer ' + api_key
        body = {
            'model': clean['model'], 'messages': [{'role': 'system', 'content': system_prompt}] + messages,
            'temperature': clean['temperature'], 'max_tokens': 900, 'stream': False,
        }
    elif protocol == 'anthropic':
        if api_key:
            headers['x-api-key'] = api_key
        headers['anthropic-version'] = '2023-06-01'
        body = {
            'model': clean['model'], 'system': system_prompt, 'messages': messages,
            'temperature': clean['temperature'], 'max_tokens': 900,
        }
    elif protocol == 'gemini':
        if api_key:
            headers['x-goog-api-key'] = api_key
        contents = []
        for message in messages:
            contents.append({'role': 'model' if message['role'] == 'assistant' else 'user', 'parts': [{'text': message['content']}]})
        body = {
            'system_instruction': {'parts': [{'text': system_prompt}]},
            'contents': contents,
            'generationConfig': {'temperature': clean['temperature'], 'maxOutputTokens': 900},
        }
    else:
        if api_key:
            headers['Authorization'] = 'Bearer ' + api_key
        body = {
            'model': clean['model'], 'messages': [{'role': 'system', 'content': system_prompt}] + messages,
            'options': {'temperature': clean['temperature']}, 'stream': False,
        }
    return endpoint, headers, body


def _text_from_content(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict) and isinstance(item.get('text'), str):
                parts.append(item['text'])
        return '\n'.join(parts).strip()
    return ''


def _responses_text(payload):
    if isinstance(payload.get('output_text'), str):
        return payload['output_text'].strip()
    parts = []
    for item in payload.get('output', []):
        if not isinstance(item, dict) or item.get('type') != 'message':
            continue
        for content in item.get('content', []):
            if not isinstance(content, dict):
                continue
            if content.get('type') in ('output_text', 'text') and isinstance(content.get('text'), str):
                parts.append(content['text'])
    return '\n'.join(parts).strip()


def parse_response(protocol, payload):
    try:
        if protocol == 'openai_responses':
            text = _responses_text(payload)
        elif protocol in ('openai', 'deepseek'):
            text = _text_from_content(payload['choices'][0]['message']['content'])
        elif protocol == 'anthropic':
            text = _text_from_content(payload['content'])
        elif protocol == 'gemini':
            text = _text_from_content(payload['candidates'][0]['content']['parts'])
        else:
            text = _text_from_content(payload['message']['content'])
    except (KeyError, IndexError, TypeError) as error:
        raise HealthApiError('模型返回了无法识别的数据格式。请检查 API 格式是否选对。') from error
    if not text:
        raise HealthApiError('模型没有返回可显示的文字。')
    return text


def _safe_error_body(raw):
    text = raw.decode('utf-8', errors='replace')[:1600]
    try:
        payload = json.loads(text)
        error = payload.get('error', payload) if isinstance(payload, dict) else payload
        if isinstance(error, dict):
            text = str(error.get('message') or error.get('detail') or error.get('type') or '')
    except ValueError:
        text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(re.sub(r'\s+', ' ', text)).strip()
    return text[:500]


def perform_chat(config, history, prompt, timeout=60, opener=urlopen):
    effective = dict(config)
    if not effective.get('api_key') and effective.get('_store'):
        effective['api_key'] = effective['_store'].load(reveal_key=True).get('api_key', '')
    endpoint, headers, body = build_request(effective, history, prompt)
    request = Request(endpoint, data=json.dumps(body, ensure_ascii=False).encode('utf-8'), headers=headers, method='POST')
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except HTTPError as error:
        detail = _safe_error_body(error.read())
        api_key = str(effective.get('api_key', '') or '')
        if api_key:
            detail = detail.replace(api_key, '••••')
        message = f'接口返回 HTTP {error.code}' + (f'：{detail}' if detail else '。')
        raise HealthApiError(message) from error
    except URLError as error:
        raise HealthApiError(f'无法连接模型接口：{str(error.reason)[:240]}') from error
    except TimeoutError as error:
        raise HealthApiError('模型响应超时，请稍后重试或调整接口地址。') from error
    except (OSError, ValueError) as error:
        raise HealthApiError('模型响应无法读取，请检查接口地址和 API 格式。') from error
    return parse_response(effective['protocol'], payload)


URGENT_PATTERNS = (
    '呼吸困难', '喘不过气', '喉咙肿', '舌头肿', '意识不清', '昏厥', '严重胸痛',
    '呕血', '便血', '误食毒', '严重过敏', 'breathing difficulty', 'throat swelling',
    'anaphylaxis', 'unconscious', 'severe chest pain', 'vomiting blood',
)


def urgent_notice(text, english=False):
    lowered = str(text or '').lower()
    if not any(pattern in lowered for pattern in URGENT_PATTERNS):
        return ''
    if english:
        return 'Safety first: these symptoms may need urgent in-person care. Contact local emergency services now and do not wait for an AI reply.'
    return '安全优先：你描述的情况可能需要紧急线下处理。请立即联系当地急救服务，不要独自等待 AI 回复。'
