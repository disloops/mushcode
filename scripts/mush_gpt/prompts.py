#!/usr/bin/env python

# MIT License
# Copyright (c) 2026 Matt Westfall (@disloops)

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import time
import subprocess
import sys
import os
import re
import logging
from datetime import datetime

logger = logging.getLogger('mush_gpt.prompts')

# Cache for loaded prompt files: {filepath: {prompts_data, load_time}}
_prompt_cache = {}
PROMPT_CACHE_DURATION = 300  # 5 minutes - reload prompts periodically

# Base directory for this module
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROMPTS_DIR = os.path.join(_BASE_DIR, 'prompts')
_DEFAULT_PROMPT_FILE = os.path.join(_BASE_DIR, 'prompts.txt')

# Characters that need astronomical data appended to their prompts
# Configured via ASTRO_CHARACTERS env var (comma-separated, case-insensitive)
_ASTRO_CHARACTERS = None  # Lazy-loaded


def _get_astro_characters():
    """Get set of characters that need astronomical data (lazy-loaded from env)."""
    global _ASTRO_CHARACTERS
    if _ASTRO_CHARACTERS is None:
        env_val = os.getenv('ASTRO_CHARACTERS', '')
        _ASTRO_CHARACTERS = set(
            x.strip().lower() for x in env_val.split(',') if x.strip()
        )
        if _ASTRO_CHARACTERS:
            logger.info(f"Astro characters configured: {_ASTRO_CHARACTERS}")
    return _ASTRO_CHARACTERS


def _is_valid_character_name(name):
    """
    Validate character name for security.
    Only alphanumeric and underscore allowed, max 64 chars.
    """
    if not name or not isinstance(name, str):
        return False
    if len(name) > 64:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_]+$', name))


def _is_safe_path(filepath, allowed_dirs):
    """
    Validate a file path is within allowed directories.
    Prevents path traversal attacks.
    """
    try:
        real_path = os.path.realpath(filepath)
        return any(real_path.startswith(os.path.realpath(d)) for d in allowed_dirs)
    except (ValueError, OSError):
        return False


def _resolve_prompt_path(prompt_file):
    """
    Resolve a prompt file path to an absolute path.

    Security: Only allows files within the mush_gpt directory tree.
    Rejects absolute paths and path traversal attempts.

    Resolution order:
    1. If relative, check prompts/ directory first
    2. Fall back to base mush_gpt directory
    3. Return default prompt file if nothing found
    """
    if not prompt_file:
        return _DEFAULT_PROMPT_FILE

    # Security: reject path traversal attempts
    if '..' in prompt_file or prompt_file.startswith('/') or prompt_file.startswith('\\'):
        logger.warning(f"Path traversal attempt rejected: {prompt_file!r}")
        return _DEFAULT_PROMPT_FILE

    # Security: only allow simple filenames (alphanumeric, underscore, dash, dot)
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', prompt_file):
        logger.warning(f"Invalid prompt filename rejected: {prompt_file!r}")
        return _DEFAULT_PROMPT_FILE

    # Try prompts/ directory first
    prompts_dir_path = os.path.join(_PROMPTS_DIR, prompt_file)
    if os.path.exists(prompts_dir_path) and _is_safe_path(prompts_dir_path, [_BASE_DIR]):
        return prompts_dir_path

    # Try base directory
    base_dir_path = os.path.join(_BASE_DIR, prompt_file)
    if os.path.exists(base_dir_path) and _is_safe_path(base_dir_path, [_BASE_DIR]):
        return base_dir_path

    logger.warning(f"Prompt file not found: {prompt_file}, using default")
    return _DEFAULT_PROMPT_FILE


def _load_prompts_file(filepath):
    """
    Load prompts from a file. Returns dict of {character: prompt_text}.

    Format:
    [CHARACTER_NAME]
    Prompt text here...

    [ANOTHER_CHARACTER]
    Another prompt...
    """
    prompts = {}

    if not os.path.exists(filepath):
        logger.error(f"Prompt file does not exist: {filepath}")
        return prompts

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split by section headers [NAME]
        sections = re.split(r'^\[([A-Z_]+)\]$', content, flags=re.MULTILINE)

        for i in range(1, len(sections), 2):
            if i + 1 < len(sections):
                section_name = sections[i].lower()
                section_content = sections[i + 1].strip()
                if section_content:
                    prompts[section_name] = section_content

        logger.debug(f"Loaded {len(prompts)} prompts from {filepath}: {list(prompts.keys())}")

    except Exception as e:
        logger.error(f"Error loading prompt file {filepath}: {e}")

    return prompts


def get_prompts_data(prompt_file=None):
    """
    Get prompts data from a file, using cache when available.

    Args:
        prompt_file: Optional path to prompt file. If None, uses default.

    Returns:
        Dict of {character: prompt_text}
    """
    global _prompt_cache

    filepath = _resolve_prompt_path(prompt_file)
    current_time = time.time()

    # Check cache
    if filepath in _prompt_cache:
        cache_entry = _prompt_cache[filepath]
        if current_time - cache_entry['load_time'] < PROMPT_CACHE_DURATION:
            return cache_entry['data']

    # Load and cache
    prompts_data = _load_prompts_file(filepath)
    _prompt_cache[filepath] = {
        'data': prompts_data,
        'load_time': current_time
    }

    return prompts_data


def clear_prompt_cache(prompt_file=None):
    """Clear the prompt cache, optionally for a specific file."""
    global _prompt_cache
    if prompt_file:
        filepath = _resolve_prompt_path(prompt_file)
        _prompt_cache.pop(filepath, None)
    else:
        _prompt_cache.clear()


def validate_prompts(prompts_data, required_prompts=None):
    """
    Validate that required prompts are present.

    Args:
        prompts_data: Dict of prompts
        required_prompts: List of required prompt names. If None, just checks
                         that at least one prompt was loaded successfully.

    Returns:
        bool: True if validation passes
    """
    if not prompts_data:
        logger.error("No prompts loaded")
        return False

    if required_prompts is None:
        # No specific requirements - just verify file loaded with content
        logger.debug(f"Prompts loaded: {list(prompts_data.keys())}")
        return True

    missing_prompts = []
    for prompt in required_prompts:
        if prompt not in prompts_data or not prompts_data[prompt].strip():
            missing_prompts.append(prompt)

    if missing_prompts:
        logger.warning(f"Missing or empty prompts: {', '.join(missing_prompts)}")
        return False

    return True


def substitute_placeholders(text):
    """Replace date/time placeholders in text."""
    if not text:
        return text

    now = datetime.now()

    text = text.replace('{today}', now.strftime('%B %d, %Y'))
    text = text.replace('{time}', now.strftime('%H:%M:%S'))
    text = text.replace('{datetime}', now.strftime('%B %d, %Y at %H:%M:%S'))

    return text


# Astronomical data cache
_astro_cache = {}
_astro_cache_time = 0
ASTRO_CACHE_DURATION = 3600  # 1 hour


def get_astronomical_context():
    """Fetch current astronomical data for astronomy-related characters."""
    global _astro_cache, _astro_cache_time

    current_time = time.time()

    if current_time - _astro_cache_time < ASTRO_CACHE_DURATION and _astro_cache:
        return _astro_cache.get('context', '')

    try:
        script_path = os.path.join(_BASE_DIR, 'astronomy_data.py')
        if not os.path.exists(script_path):
            logger.debug("astronomy_data.py not found, skipping astronomical context")
            return ""

        result = subprocess.run(
            [sys.executable, script_path, '--bot'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and result.stdout.strip():
            summary = result.stdout.strip()
            context = f"\n\nCurrent Astronomical Data: {summary}"
            _astro_cache = {'context': context, 'summary': summary}
            _astro_cache_time = current_time
            return context
        else:
            return "\n\nCurrent Astronomical Data: Unable to fetch data"
    except subprocess.TimeoutExpired:
        logger.error("Astronomy data fetch timed out")
        return "\n\nCurrent Astronomical Data: Timeout fetching data"
    except Exception as e:
        logger.error(f"Error fetching astronomical data: {e}")
        return "\n\nCurrent Astronomical Data: Error fetching data"


def get_prompt(character, prompt_file=None):
    """
    Get the prompt for a specific character.

    Args:
        character: Character name (validated for security)
        prompt_file: Optional path to prompt file

    Returns:
        The formatted prompt string for the character, or None if invalid/not found
    """
    # Security: validate character name
    if not _is_valid_character_name(character):
        logger.warning(f"Invalid character name rejected: {character!r}")
        return None

    character = character.lower()
    prompts_data = get_prompts_data(prompt_file)

    if character not in prompts_data:
        logger.warning(f"Unknown character: {character}")
        return None

    base_prompt = prompts_data[character]
    base_prompt = substitute_placeholders(base_prompt)

    # Append astronomical data if this character is configured for it
    if character in _get_astro_characters():
        astro_context = get_astronomical_context()
        base_prompt = f"{base_prompt}{astro_context}"

    return base_prompt


def get_character_context_interests(character, prompt_file=None):
    """
    Extract CONTEXT and INTERESTS sections from a character's prompt.
    Used for relevance analysis.

    Args:
        character: Character name (validated for security)
        prompt_file: Optional path to prompt file

    Returns:
        Combined CONTEXT and INTERESTS string, or None if invalid character
    """
    # Security: validate character name
    if not _is_valid_character_name(character):
        logger.warning(f"Invalid character name rejected: {character!r}")
        return None

    character = character.lower()
    prompts_data = get_prompts_data(prompt_file)
    full_prompt = prompts_data.get(character, '')

    if not full_prompt:
        return None

    sections = {}
    section_parts = re.split(r'^([A-Z_]+):\s*$', full_prompt, flags=re.MULTILINE)
    for i in range(1, len(section_parts), 2):
        if i + 1 < len(section_parts):
            section_name = section_parts[i].upper()
            section_content = section_parts[i + 1].strip()

            lines = section_content.split('\n')
            content_lines = []
            for line in lines:
                if re.match(r'^[A-Z_]+:\s*$', line.strip()):
                    break
                content_lines.append(line)

            clean_content = '\n'.join(content_lines).strip()
            if clean_content:
                sections[section_name] = clean_content

    context = sections.get('CONTEXT', '').strip()
    interests = sections.get('INTERESTS', '').strip()
    combined = f"CONTEXT: {context}\n\nINTERESTS: {interests}"
    return substitute_placeholders(combined)


def get_valid_prompts(prompt_file=None):
    """
    Get list of valid character names from a prompt file.

    Args:
        prompt_file: Optional path to prompt file

    Returns:
        List of character names available in the prompt file
    """
    prompts_data = get_prompts_data(prompt_file)
    return list(prompts_data.keys())


def list_prompt_files():
    """List available prompt files in the prompts directory."""
    files = []

    # Check default file
    if os.path.exists(_DEFAULT_PROMPT_FILE):
        files.append(('prompts.txt', _DEFAULT_PROMPT_FILE))

    # Check prompts directory
    if os.path.exists(_PROMPTS_DIR):
        for filename in os.listdir(_PROMPTS_DIR):
            if filename.endswith('.txt'):
                filepath = os.path.join(_PROMPTS_DIR, filename)
                files.append((filename, filepath))

    return files
