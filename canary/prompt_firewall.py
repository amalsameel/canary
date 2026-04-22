"""Prompt firewall: regex + entropy + Luhn secret & PII detection.

Returns a list of PromptFinding objects. Each finding carries the matched text
(used only for redacted display — never logged raw).
"""
import re
import math
import string
from dataclasses import dataclass


@dataclass
class PromptFinding:
    kind: str            # secret | pii | path | entropy
    severity: str        # CRITICAL | HIGH | MEDIUM
    description: str
    matched: str         # raw matched text; redacted before display
    score: int           # risk points


# ---------------------------------------------------------------------------
# Known-format secrets. Order matters: most specific first.
# ---------------------------------------------------------------------------
SECRET_PATTERNS: list[tuple[str, str, str, int]] = [
    (r'sk-[A-Za-z0-9_\-]{20,}',              'API key',                            'CRITICAL', 40),
    (r'ghp_[A-Za-z0-9]{30,40}',              'GitHub personal access token',       'CRITICAL', 40),
    (r'gh[osu]_[A-Za-z0-9]{30,40}',          'GitHub OAuth/server/user token',     'CRITICAL', 40),
    (r'glpat-[A-Za-z0-9_\-]{20,}',           'GitLab personal access token',       'CRITICAL', 40),
    (r'xox[baprs]-[A-Za-z0-9\-]{10,}',       'Slack token',                        'CRITICAL', 40),
    (r'AKIA[0-9A-Z]{16}',                    'AWS access key ID',                  'CRITICAL', 40),
    (r'AIza[0-9A-Za-z_\-]{35}',              'Google API key',                     'CRITICAL', 40),
    (r'hf_[A-Za-z0-9]{30,}',                 'Hugging Face token',                 'CRITICAL', 40),
    (r'(rk|sk|pk)_live_[A-Za-z0-9]{20,}',    'Stripe live key',                    'CRITICAL', 40),
    (r'(?i)(password|passwd|pwd)\s*[=:]\s*\S{6,}',     'Inline password assignment', 'HIGH', 30),
    (r'(?i)(secret|api[_-]?key|token)\s*[=:]\s*\S{8,}', 'Inline secret assignment',  'HIGH', 30),
]

# ---------------------------------------------------------------------------
# PII patterns.
# ---------------------------------------------------------------------------
PII_PATTERNS: list[tuple[str, str, str, int]] = [
    (r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', 'Email address',    'MEDIUM', 20),
    (r'\b\d{3}-\d{2}-\d{4}\b',                          'SSN',              'CRITICAL', 40),
    (r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b',                'Phone number',     'MEDIUM', 10),
]

# Credit card candidates (pre-Luhn): 13–19 digits with optional separators.
CC_CANDIDATE = re.compile(r'\b(?:\d[ -]?){12,18}\d\b')

# ---------------------------------------------------------------------------
# Sensitive path references.
# ---------------------------------------------------------------------------
PATH_PATTERNS: list[tuple[str, str, str, int]] = [
    (r'/etc/passwd',            'System password file path',   'HIGH',     25),
    (r'/etc/shadow',            'System shadow file path',     'CRITICAL', 40),
    (r'~/\.ssh/',               'SSH directory path',          'HIGH',     25),
    (r'(?<![A-Za-z0-9_])\.env(?![A-Za-z0-9_])', '.env file reference',     'HIGH', 25),
    (r'\bid_(?:rsa|ed25519|dsa)\b', 'Private key file reference', 'CRITICAL', 40),
    (r'/root/',                 'Root home directory path',    'MEDIUM',   15),
]

# ---------------------------------------------------------------------------
# Sensitive business context keywords.
# ---------------------------------------------------------------------------
CONTEXT_PATTERNS: list[tuple[str, str, str, int]] = [
    (r'(?i)\bproprietary\b',                    'Proprietary information',      'MEDIUM', 20),
    (r'(?i)\bconfidential\b',                   'Confidential information',     'MEDIUM', 20),
    (r'(?i)\btrade\s+secret',                   'Trade secret reference',       'HIGH',   30),
    (r'(?i)\bclassified\b',                     'Classified information',       'HIGH',   30),
    (r'(?i)\binternal\s+(?:use\s+)?only\b',     'Internal-only content',        'MEDIUM', 20),
    (r'(?i)\bnot\s+for\s+(?:public\s+)?distribution\b', 'Distribution-restricted content', 'MEDIUM', 20),
    (r'(?i)\bunder\s+(?:an?\s+)?nda\b',         'NDA-protected content',        'HIGH',   30),
    (r'(?i)\bdo\s+not\s+(?:share|disclose|distribute)\b', 'Disclosure-restricted content', 'HIGH', 30),
    (r'(?i)\bprivileged\s+(?:and\s+)?confidential\b', 'Privileged & confidential', 'HIGH', 30),
    (r'(?i)\bembargo(?:ed)?\b',                 'Embargoed content',            'HIGH',   30),
    (r'(?i)\bpatent\s+pending\b',               'Patent-pending IP',            'MEDIUM', 15),
]

# Entropy-check allowlist: strings matching these are NOT flagged as entropy secrets.
ENTROPY_ALLOW = [
    re.compile(r'^[0-9a-f]{40}$'),                    # git SHA-1
    re.compile(r'^[0-9a-f]{64}$'),                    # SHA-256
    re.compile(r'^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$'),  # UUID
    re.compile(r'^sha(?:256|512):[0-9a-f]+$'),        # hash with prefix
]


def shannon_entropy(s: str) -> float:
    """Shannon entropy of a string in bits per character."""
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    length = len(s)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def luhn_valid(number: str) -> bool:
    """Luhn checksum for credit-card candidates. Digits only."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _is_allowed_entropy(token: str) -> bool:
    return any(r.match(token) for r in ENTROPY_ALLOW)


def _severity_bonus(severity: str) -> int:
    return {
        "CRITICAL": 8,
        "HIGH": 5,
        "MEDIUM": 2,
    }.get(severity, 0)


def _description_bonus(kind: str, description: str) -> int:
    desc = description.lower()
    bonus = 0

    if kind == "secret":
        bonus += 6

    if any(term in desc for term in ("api key", "access token", "personal access token", "live key")):
        bonus += 10
    elif any(term in desc for term in ("private key", "shadow", "password", "credit card", "ssn")):
        bonus += 7
    elif any(term in desc for term in ("email", "phone")):
        bonus += 1

    return bonus


def _match_bonus(matched: str) -> int:
    token = matched.strip()
    bonus = 0

    if len(token) >= 20:
        bonus += min(6, max(0, (len(token) - 20) // 6))

    entropy = shannon_entropy(token)
    if entropy >= 3.5:
        bonus += min(8, max(0, round((entropy - 3.5) * 3)))

    return bonus


def _finding_score(kind: str, severity: str, description: str, matched: str, base_score: int) -> int:
    score = base_score
    score += _severity_bonus(severity)
    score += _description_bonus(kind, description)
    score += _match_bonus(matched)

    if kind == "secret":
        return min(score, 85)
    if kind == "pii":
        return min(score, 70)
    if kind == "path":
        return min(score, 75)
    if kind == "context":
        return min(score, 55)
    return min(score, 65)


def scan_prompt(text: str) -> list[PromptFinding]:
    findings: list[PromptFinding] = []
    seen_spans: set[tuple[int, int]] = set()

    def _add(kind, severity, description, match_text, score, span):
        # Avoid double-counting the same span
        if span in seen_spans:
            return
        seen_spans.add(span)
        findings.append(
            PromptFinding(
                kind,
                severity,
                description,
                match_text,
                _finding_score(kind, severity, description, match_text, score),
            )
        )

    for pattern, description, severity, score in SECRET_PATTERNS:
        for m in re.finditer(pattern, text):
            _add("secret", severity, description, m.group(), score, m.span())

    for pattern, description, severity, score in PII_PATTERNS:
        for m in re.finditer(pattern, text):
            _add("pii", severity, description, m.group(), score, m.span())

    # Credit card: regex + Luhn
    for m in CC_CANDIDATE.finditer(text):
        raw = m.group()
        if luhn_valid(raw):
            _add("pii", "HIGH", "Credit card number (Luhn-valid)", raw, 30, m.span())

    for pattern, description, severity, score in PATH_PATTERNS:
        for m in re.finditer(pattern, text):
            _add("path", severity, description, m.group(), score, m.span())

    for pattern, description, severity, score in CONTEXT_PATTERNS:
        for m in re.finditer(pattern, text):
            _add("context", severity, description, m.group(), score, m.span())

    # Entropy sweep on whitespace-separated tokens
    for m in re.finditer(r'\S+', text):
        token = m.group().strip(string.punctuation)
        if len(token) < 20 or len(token) > 200:
            continue
        if _is_allowed_entropy(token):
            continue
        if shannon_entropy(token) > 4.5:
            if not any(f.matched == token for f in findings):
                _add("entropy", "HIGH",
                     "High-entropy string (possible secret)",
                     token, 25, m.span())

    return findings
