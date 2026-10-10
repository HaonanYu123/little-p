"""Reject secrets and user-specific local paths before publishing."""
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    '', '.bat', '.cjs', '.css', '.html', '.ini', '.iss', '.js', '.json',
    '.md', '.ps1', '.py', '.spec', '.txt', '.yml', '.yaml',
}
PATTERNS = {
    'OpenAI/DeepSeek-style API key': re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b'),
    'Google API key': re.compile(r'\bAIza[A-Za-z0-9_-]{20,}\b'),
    'GitHub token': re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b'),
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'Windows user profile path': re.compile(r'(?i)\b[A-Z]:\\Users\\(?!Public\\)[^\\\r\n]+\\'),
}


def candidate_files():
    output = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
        cwd=ROOT,
    )
    for raw in output.split(b'\0'):
        if not raw:
            continue
        path = ROOT / raw.decode('utf-8')
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            yield path


findings = []
for path in candidate_files():
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        continue
    for label, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            line = text.count('\n', 0, match.start()) + 1
            findings.append(f'{path.relative_to(ROOT)}:{line}: {label}')

if findings:
    raise SystemExit('Release privacy scan failed:\n' + '\n'.join(findings))

print('Release privacy scan passed: no API keys, private keys, or user-profile paths found.')
