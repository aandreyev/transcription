# Prompting Framework

This document explains how prompts are resolved and applied during processing.

## Overview
The application uses three prompt stages:
- Summary (builds the Markdown report)
- Naming (generates the final filename string)
- Validation (optionally corrects the filename string)

Each stage loads a global prompt from `prompts/*.md`, and may be overridden per folder with dedicated files.

## Global prompt files
- `prompts/summary.md`
- `prompts/naming.md`
- `prompts/filename-validation.md`

These templates are used when no folder override is present.

## Folder overrides (per subfolder)
Place a Markdown file in or above the audio file’s folder. The resolver searches upward for the first match:
- Summary: `instructions.md`, then `summary.md`, then `.instructions.md`
- Naming: `naming.md`, then `.naming.md`
- Validation: `filename-validation.md`, then `.filename-validation.md`

Only the matching file for a stage is used (e.g., naming uses `naming.md`, not `instructions.md`).

## Front matter (optional)
At the very top of any override file, you may include YAML front matter to configure modes and OpenAI parameters.

Example:
```md
---
openai:
  model: gpt-4o
  temperature: 0.3
prompts:
  summary_mode: replace     # or: append
  naming_mode: replace      # or: append
  validation_mode: replace  # or: append
---

Folder-specific instructions...
```

- `openai.model`: model name for that stage (defaults to config `openai.model`)
- `openai.temperature`: temperature for that stage (defaults to config `openai.temperature`)
- `prompts.summary_mode`: how to combine folder summary with global (`replace` default when provided, or `append`)
- `prompts.naming_mode`: how to combine folder naming with global (`replace` or `append`)
- `prompts.validation_mode`: how to combine folder validation with global (`replace` or `append`)

Notes:
- Place front matter exactly at the start of the file with `---` as first and last lines.
- If front matter is omitted, the file body still works; default modes apply.

## Combination rules
- Summary stage
  - Global: `prompts/summary.md`
  - Folder override: `instructions.md` or `summary.md`
  - Mode:
    - `replace`: use folder text only
    - `append`: global summary + "Folder Instructions" + folder text
- Naming stage
  - Global: `prompts/naming.md`
  - Folder override: `naming.md`
  - Mode:
    - `replace`: use folder text only
    - `append`: global naming + "Folder Instructions" + folder text
- Validation stage
  - Global: `prompts/filename-validation.md`
  - Folder override: `filename-validation.md`
  - Mode:
    - `replace`: use folder text only
    - `append`: global validation + "Folder Validation Rules" + folder text

## Placeholders
Before sending a prompt to OpenAI, placeholders are substituted:
- `{original_filename}`: the audio file name
- `{duration_minutes}`: rounded minutes (or `Unknown`)
- `{transcript}`: full transcript (used by summary)
- `{transcript_summary}`: first ~500 characters with `...` (used by naming/validation)

You can use these placeholders in global and folder prompt files. If a placeholder is missing in context, it is left as-is.

## Naming pipeline
1) Build naming prompt (global + optional folder `naming.md` per mode)
2) Model returns a single line "complete filename"
3) Validation prompt (global + optional folder validation per mode) fixes or returns `VALID`
4) `IntelligentFileNamer` cleans the filename (filesystem safety, de-duplication)
5) The final name is used for the output Markdown document. The original audio is moved (not renamed by default).

## Configuration keys
- `openai.model`, `openai.temperature`, `openai.max_tokens` (global defaults)
- `prompt_files.summary_candidates`
- `prompt_files.naming_candidates`
- `prompt_files.validation_candidates`

## Logging
During processing, logs indicate:
- Which folder files were used for summary/naming/validation and their lengths
- Which modes were applied (replace/append)
- Final OpenAI parameters (model, temperature)

## Tips
- Prefer `replace` for `naming.md` to avoid prompt bloat; use `append` to add a small nuance.
- Keep validation lightweight; most fixes are handled by the validation prompt + final cleaner.
- If you don’t want full transcript in a folder prompt, omit `{transcript}` and rely on `{transcript_summary}`.
