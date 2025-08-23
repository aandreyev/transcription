from .config_manager import ConfigManager
from .logger import get_logger, log_info, log_error, log_warning, log_debug

__all__ = ['ConfigManager', 'get_logger', 'log_info', 'log_error', 'log_warning', 'log_debug']


def find_prompt_file(start_path: str, candidate_names: list[str]):
    """Search upward from the file's directory for a prompt file.
    Returns absolute path if found, else None.
    """
    import os
    if not start_path:
        return None
    directory = os.path.dirname(os.path.abspath(start_path))
    while True:
        for name in candidate_names or []:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return None


def resolve_folder_prompt(file_path: str, kind: str, config: ConfigManager | None = None):
    """Resolve folder-level prompt for a given kind ('summary'|'naming'|'filename-validation').
    Returns (overrides_dict, body_text, path or None).
    """
    cfg = config or ConfigManager()
    candidates_map = {
        'summary': cfg.get('prompt_files.summary_candidates', ['instructions.md', 'summary.md', '.instructions.md']),
        'naming': cfg.get('prompt_files.naming_candidates', ['naming.md', '.naming.md']),
        'filename-validation': cfg.get('prompt_files.validation_candidates', ['filename-validation.md', '.filename-validation.md'])
    }
    names = candidates_map.get(kind, [])
    path = find_prompt_file(file_path, names)
    if not path:
        return {}, '', None
    overrides, body = load_prompt_overrides(path)
    return overrides or {}, body or '', path


def load_prompt_overrides(prompt_path: str):
    """Load YAML front-matter (if present) and body text from a markdown file.
    Returns (overrides_dict, body_text).
    """
    overrides = {}
    body = ""
    if not prompt_path:
        return overrides, body
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if content.startswith('---'):
            end = content.find('\n---', 3)
            if end != -1:
                import yaml
                fm_text = content[3:end].strip()
                overrides = yaml.safe_load(fm_text) or {}
                body = content[end+4:].lstrip('\n')
            else:
                body = content
        else:
            body = content
    except Exception:
        overrides = {}
        body = ""
    return overrides, body


def read_prompt_file(kind: str, config: ConfigManager | None = None) -> str:
    """Read a prompt markdown file from prompts/{kind}.md; fallback to config if missing.
    Recognized kinds: 'summary', 'naming', 'filename-validation'.
    """
    import os
    mapping = {
        'summary': 'summary.md',
        'naming': 'naming.md',
        'filename-validation': 'filename-validation.md',
    }
    fname = mapping.get(kind, f"{kind}.md")
    path = os.path.join(os.getcwd(), 'prompts', fname)
    try:
        if os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception:
        pass
    # Fallback to config keys for backward compatibility
    cfg = config or ConfigManager()
    if kind == 'summary':
        return cfg.get('prompts.summary', '')
    if kind == 'naming':
        return cfg.get('prompts.naming_extraction', '')
    if kind == 'filename-validation':
        return cfg.get('prompts.filename_validation', '')
    return ''
