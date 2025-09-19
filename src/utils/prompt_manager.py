from __future__ import annotations

from typing import Dict, Tuple, Optional
from .config_manager import ConfigManager


class _SafeDict(dict):
    def __missing__(self, key):  # type: ignore[override]
        return '{' + key + '}'


def build_transcript_summary(transcript: str, max_len: int = 500) -> str:
    if not transcript:
        return ''
    return transcript[:max_len] + '...' if len(transcript) > max_len else transcript


def safe_format(template: str, placeholders: Dict[str, object]) -> str:
    try:
        return template.format_map(_SafeDict(**(placeholders or {})))
    except Exception:
        # Never fail prompt building due to formatting; return as-is
        return template


def combine_prompt(
    *,
    base_template: str,
    folder_body: str,
    placeholders: Dict[str, object],
    mode: str,
    section_heading: str,
) -> str:
    base = safe_format(base_template or '', placeholders)
    if not folder_body:
        return base
    folder = safe_format(folder_body, placeholders)
    m = (mode or 'replace').lower()
    if m == 'append':
        return f"{base}\n\n# {section_heading}\n{folder}\n"
    # default replace
    return folder


def resolve_openai_params(
    *,
    config: ConfigManager,
    overrides: Optional[Dict[str, object]] = None,
) -> Tuple[str, float, int]:
    ov = (overrides or {}).get('openai', {}) if isinstance(overrides, dict) else {}
    # Single source of truth for model: config.yaml
    model = config.get('openai.model', 'gpt-4o')
    temperature = ov.get('temperature', config.get('openai.temperature', 0.7))
    max_tokens = config.get('openai.max_tokens', 2000)
    try:
        temperature = float(temperature)
    except Exception:
        temperature = 0.7
    try:
        max_tokens = int(max_tokens)
    except Exception:
        max_tokens = 2000
    return str(model), temperature, max_tokens


