"""Verify cold start and repeated protocol summons against the packaged app."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from desktop_host import request_pet


EXE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'dist' / 'LittleP' / 'LittleP.exe'


def wait_for(test, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        status = request_pet('status', timeout=.5)
        if status and test(status):
            return status
        time.sleep(.12)
    raise TimeoutError('Packaged desktop pet did not reach the expected state')


request_pet('dismiss')
time.sleep(.4)
first = subprocess.Popen([
    str(EXE),
    'littlep://summon?character=pink-robot&emotion=02&request=verify-cold',
])

try:
    cold = wait_for(lambda value: value.get('ready'))
    subprocess.run([
        str(EXE),
        'littlep://summon?character=robot&emotion=13&request=verify-repeat',
    ], check=True, timeout=20)
    repeated = wait_for(
        lambda value: value.get('ready')
        and value.get('state', {}).get('character') == 'robot'
        and value.get('state', {}).get('emotion') == '13'
    )
    assert cold['pid'] == repeated['pid'], 'Repeated summon created a second pet process'
    report = {
        'passed': 3,
        'results': [
            'Packaged app completes a cold protocol launch',
            'Repeated protocol summon reaches the running instance',
            'Repeated summon preserves a single desktop pet process',
        ],
        'pid': repeated['pid'],
        'state': repeated['state'],
    }
    (ROOT / 'output' / 'packaged-summon-verification.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(json.dumps(report, ensure_ascii=True), flush=True)
finally:
    request_pet('dismiss')
    try:
        first.wait(timeout=8)
    except subprocess.TimeoutExpired:
        first.terminate()
