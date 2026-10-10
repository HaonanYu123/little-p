"""Offline checks for health guardrails, provider adapters, and DPAPI storage."""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from desktop.health_api import (
    HealthApiError, HealthSettingsStore, build_request, parse_response, perform_chat,
    sync_native_skill, trim_history, urgent_notice, validate_config,
)


results = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    results.append(name)


base = {'endpoint': 'https://example.test/v1/chat/completions', 'model': 'any-model', 'temperature': .3}

try:
    validate_config(dict(base, protocol='openai'))
    check('HTTPS custom endpoints and arbitrary model names are accepted', True)
    validate_config(dict(base, protocol='ollama', endpoint='http://127.0.0.1:11434/api/chat'))
    check('Plain HTTP is restricted to a local model endpoint', True)
    try:
        validate_config(dict(base, protocol='openai', endpoint='http://example.test/v1/chat/completions'))
        raise AssertionError('Remote HTTP should be rejected')
    except HealthApiError:
        check('Remote model endpoints must use HTTPS', True)
    try:
        validate_config(dict(base, protocol='gemini', endpoint='https://example.test/generate?key=plain-secret'))
        raise AssertionError('Secrets in endpoint URLs should be rejected')
    except HealthApiError:
        check('Secrets cannot be stored in plaintext endpoint URLs', True)

    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'health.json'
        store = HealthSettingsStore(path)
        secret = 'test-key-that-must-never-appear-in-plain-text'
        store.save(dict(base, protocol='openai'), api_key=secret)
        raw = path.read_text(encoding='utf-8')
        check('The API key is not stored in plaintext', secret not in raw and 'api_key_dpapi' in raw)
        check('DPAPI restores the key only for the current Windows user', store.load(reveal_key=True)['api_key'] == secret)
        store.save(dict(base, protocol='openai', model='another-model'), api_key=None)
        check('Saving other settings preserves the encrypted key', store.load(reveal_key=True)['api_key'] == secret)
        store.clear_key()
        check('Users can remove the locally saved key', not store.load()['has_api_key'])

    fixtures = {
        'openai_responses': {'output': [{'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'OpenAI Responses'}]}]},
        'openai': {'choices': [{'message': {'content': 'OpenAI-compatible'}}]},
        'deepseek': {'choices': [{'message': {'content': 'DeepSeek'}}]},
        'anthropic': {'content': [{'type': 'text', 'text': 'Anthropic'}]},
        'gemini': {'candidates': [{'content': {'parts': [{'text': 'Gemini'}]}}]},
        'ollama': {'message': {'role': 'assistant', 'content': 'Ollama'}},
    }
    expected_text = {'openai_responses': 'OpenAI Responses', 'openai': 'OpenAI-compatible', 'deepseek': 'DeepSeek', 'anthropic': 'Anthropic', 'gemini': 'Gemini', 'ollama': 'Ollama'}
    for protocol, payload in fixtures.items():
        endpoint = {
            'openai_responses': 'https://api.openai.com/v1/responses',
            'openai': 'https://example.test/v1/chat/completions',
            'deepseek': 'https://api.deepseek.com/chat/completions',
            'anthropic': 'https://api.anthropic.com/v1/messages',
            'gemini': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            'ollama': 'http://localhost:11434/api/chat',
        }[protocol]
        config = dict(base, protocol=protocol, endpoint=endpoint, api_key='local-secret')
        if protocol == 'openai_responses':
            config['skill_id'] = 'skill_test'
        url, headers, body = build_request(config, [{'role': 'assistant', 'content': 'Earlier answer'}], 'My meal', system_prompt='Health skill')
        check(f'{protocol} builds a valid non-streaming request', bool(url and headers.get('Content-Type') and body.get('model', 'gemini')))
        check(f'{protocol} response text is supported', parse_response(protocol, payload) == expected_text[protocol])
        check(f'{protocol} never puts the API key in the JSON body', 'local-secret' not in json.dumps(body))
        if protocol == 'deepseek':
            check('DeepSeek uses its official endpoint with Bearer authentication', url == 'https://api.deepseek.com/chat/completions' and headers['Authorization'] == 'Bearer local-secret')
        if protocol == 'openai_responses':
            check('Responses attaches the uploaded Skill to hosted shell', body['tools'][0]['environment']['skills'][0]['skill_id'] == 'skill_test')
            check('Responses keeps health safety rules in high-priority instructions', body['instructions'].startswith('Health skill'))
            check('Responses disables server-side conversation storage', body['store'] is False)

    class SkillStore:
        saved = None

        def save_skill_reference(self, skill_id, digest):
            self.saved = (skill_id, digest)

    class FakeSkillResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({'id': 'skill_uploaded'}).encode('utf-8')

    def fake_skill_opener(request, timeout):
        check('Skill upload is restricted to the official OpenAI endpoint', request.full_url == 'https://api.openai.com/v1/skills')
        check('Skill upload uses a bounded multipart request', timeout == 9 and request.headers['Content-type'].startswith('multipart/form-data;'))
        return FakeSkillResponse()

    skill_store = SkillStore()
    skill_config = {
        'protocol': 'openai_responses', 'endpoint': 'https://api.openai.com/v1/responses',
        'model': 'any-model', 'temperature': .3, 'api_key': 'local-secret', '_store': skill_store,
    }
    check('Explicit Skill sync stores the returned reference', sync_native_skill(skill_config, timeout=9, opener=fake_skill_opener) == 'skill_uploaded' and skill_store.saved[0] == 'skill_uploaded')
    try:
        sync_native_skill(dict(skill_config, endpoint='https://example.test/v1/responses'), opener=fake_skill_opener)
        raise AssertionError('Third-party Skill uploads should be rejected')
    except HealthApiError:
        check('Skill contents cannot be uploaded to a third-party endpoint', True)

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(fixtures['openai']).encode('utf-8')

    def fake_opener(request, timeout):
        check('The transport sends JSON with a bounded timeout', request.get_method() == 'POST' and timeout == 7 and request.data.startswith(b'{'))
        return FakeResponse()

    check('The provider-neutral transport returns parsed text', perform_chat(dict(base, protocol='openai'), [], 'Lunch', timeout=7, opener=fake_opener) == 'OpenAI-compatible')

    history = [{'role': 'user', 'content': str(index)} for index in range(30)]
    check('Conversation context is bounded in memory', len(trim_history(history)) == 12)
    check('Urgent allergy symptoms trigger a local warning before the model', bool(urgent_notice('我严重过敏，现在呼吸困难')))
    print(json.dumps({'passed': len(results), 'results': results}, ensure_ascii=False), flush=True)
except Exception as error:
    print(json.dumps({'passed': len(results), 'results': results, 'failure': str(error)}, ensure_ascii=False), flush=True)
    raise
