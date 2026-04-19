"""Prompt intent auditor — analyses a user prompt before it reaches an LLM agent."""
import json
import os
import re
from dataclasses import dataclass

_SYSTEM_PROMPT = """\
You are a security analyst for AI coding agent sessions.

A user is about to send a prompt to Claude Code.
Analyse the prompt and predict what the agent will do in response.

Respond ONLY with a valid JSON object. No markdown, no explanation outside the JSON.

JSON fields:
- "risk": one of SAFE, LOW, MEDIUM, HIGH, CRITICAL
- "intent": brief label of what the user is asking for (e.g. "refactor auth module", \
"install packages", "modify database schema")
- "likely_actions": one sentence — what the agent will probably do
- "commands": comma-separated list of potentially risky commands the agent might run, \
or "none"
- "concern": one sentence on the main safety concern, or "none"

Risk guidelines:
- SAFE: reading/explaining code, writing docs, adding comments
- LOW: simple local edits, adding tests, renaming variables
- MEDIUM: installing packages, editing config files, making network calls, file moves
- HIGH: modifying auth or security code, schema changes, deleting files, \
editing environment variables
- CRITICAL: system-level ops, direct credential handling, destructive migrations, \
wiping data"""

_PATTERN_INTENTS = [
    # CRITICAL
    (r'\b(wipe|purge|drop\s+table|truncate\s+table|rm\s+-rf)\b',
     "CRITICAL", "destructive operation",    "agent may permanently destroy data or files"),
    # HIGH — checked before lower-risk patterns so they take priority
    (r'\b(auth(?:entication|oriz\w+)?|jwt|oauth|session.?token|login|logout)\b',
     "HIGH",     "auth / security change",   "agent will modify authentication or authorisation logic"),
    (r'\b(secret|password|passphrase|api.?keys?|credentials?|private.?key)\b',
     "HIGH",     "credential handling",      "agent may read or write sensitive credentials"),
    (r'\b(sudo|chmod|chown|passwd|useradd|usermod)\b',
     "HIGH",     "privilege change",         "agent may modify system permissions or user accounts"),
    (r'\b(rm|delete|drop|remove)\b.{0,30}\b(file|dir|folder|table|record|row)',
     "HIGH",     "destructive operation",    "agent may delete files, directories, or database records"),
    (r'\b(migrate|migration|schema|alter\s+table|add\s+column|drop\s+column)\b',
     "HIGH",     "database schema change",   "agent will modify database structure"),
    # MEDIUM
    (r'\b(install|pip\s+install|npm\s+install|brew\s+install|apt.get|yarn\s+add|cargo\s+add)\b',
     "MEDIUM",   "package install",          "agent will install third-party packages"),
    (r'\b(curl|wget|fetch|http|https|api|endpoint|webhook)\b',
     "MEDIUM",   "network operation",        "agent will make outbound network requests"),
    (r'\b(env(?:ironment)?|\.env|config|settings|\.yaml|\.toml|\.ini)\b',
     "MEDIUM",   "config change",            "agent will modify configuration or environment files"),
    # LOW
    (r'\b(refactor|rename|move|reorganis[e]?|restructure)\b',
     "LOW",      "code restructure",         "agent will reorganise existing code"),
    (r'\b(tests?|spec|coverage|assert|mock|fixture)\b',
     "LOW",      "testing",                  "agent will write or run tests"),
    (r'\b(fix|bug|issue|error|crash|exception)\b',
     "LOW",      "bug fix",                  "agent will attempt to fix a reported problem"),
    # SAFE
    (r'\b(explain|describe|summaris[e]?|summarize|what\s+does|how\s+does|why\s+is)\b',
     "SAFE",     "explanation",              "agent will explain or describe code"),
    (r'\b(document|docstring|comment|readme|changelog)\b',
     "SAFE",     "documentation",            "agent will write documentation"),
]


@dataclass
class AuditResult:
    risk: str
    intent: str
    likely_actions: str
    commands: str
    concern: str
    via_llm: bool


_QUESTION_RE = re.compile(
    r'^(explain|describe|what|how|why|when|where|who|can you|could you|show me|tell me|summarise|summarize)',
    re.IGNORECASE,
)


def _pattern_audit(prompt: str) -> AuditResult:
    lower = prompt.strip().lower()

    # Interrogative / explanation prompts are always SAFE regardless of subject matter
    if _QUESTION_RE.match(prompt.strip()):
        return AuditResult(
            risk="SAFE",
            intent="explanation",
            likely_actions="agent will explain or describe the requested topic",
            commands="none",
            concern="none",
            via_llm=False,
        )

    for pattern, risk, intent, concern in _PATTERN_INTENTS:
        if re.search(pattern, lower):
            return AuditResult(
                risk=risk,
                intent=intent,
                likely_actions=f"agent will act on: {prompt[:80]}",
                commands="unknown — pattern-based analysis only",
                concern=concern,
                via_llm=False,
            )
    return AuditResult(
        risk="SAFE",
        intent="general task",
        likely_actions=f"agent will act on: {prompt[:80]}",
        commands="none",
        concern="none",
        via_llm=False,
    )


def audit_prompt(prompt: str) -> AuditResult:
    """Analyse a user prompt using Granite (online) or pattern rules (local)."""
    use_local = os.environ.get("IBM_LOCAL", "false").strip().lower() == "true"

    if not use_local:
        try:
            from .ibm.generate import chat_completion

            raw = chat_completion(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": f"Analyse this prompt:\n\n{prompt}"},
                ],
                max_tokens=256,
            )
            raw = re.sub(r"^```(?:json)?\n?", "", raw.strip())
            raw = re.sub(r"\n?```$", "", raw)
            data = json.loads(raw)
            return AuditResult(
                risk=data.get("risk", "MEDIUM"),
                intent=data.get("intent", "unknown"),
                likely_actions=data.get("likely_actions", ""),
                commands=data.get("commands", "none"),
                concern=data.get("concern", "none"),
                via_llm=True,
            )
        except Exception:
            pass

    return _pattern_audit(prompt)
