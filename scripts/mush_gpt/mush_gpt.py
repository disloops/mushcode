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

__author__ = 'Matt Westfall'
__version__ = '2.0'
__email__ = 'disloops@gmail.com'


import time
import os
import sys
import re
import logging
from logging.handlers import RotatingFileHandler

# Check required dependencies before proceeding
try:
    from flask import Flask, request, jsonify
except ImportError:
    print("ERROR: flask not installed. Run: pip install flask", file=sys.stderr)
    sys.exit(1)

from prompts import get_prompt, get_valid_prompts, get_character_context_interests
from providers import get_provider, FinishReason

def load_env_file(filepath):
    """Load environment variables from a .env file"""
    env_vars = {}
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

env_vars = load_env_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mush_gpt.env'))
for key, value in env_vars.items():
    os.environ[key] = value


def validate_config():
    """Validate required configuration. Exits with error if missing."""
    missing = []

    # Core required settings
    required_core = [
        'AUTH_KEY',
        'LLM_PROVIDER',
        'MAX_COMPLETION_TOKENS',
        'MAX_INPUT_LENGTH',
        'LOG_LEVEL',
        'LOG_MAX_SIZE',
        'LOG_BACKUP_COUNT',
        'FLASK_HOST',
        'FLASK_PORT',
        'FLASK_DEBUG',
    ]

    for var in required_core:
        if not os.getenv(var):
            missing.append(var)

    # Provider-specific settings (default + optional /cmd override)
    providers_needed = set()
    default_provider_name = os.getenv('LLM_PROVIDER', '').lower()
    if default_provider_name:
        providers_needed.add(default_provider_name)

    cmd_provider_name = os.getenv('CMD_LLM_PROVIDER', '').strip().lower()
    if cmd_provider_name:
        if cmd_provider_name not in ('openai', 'gemini'):
            missing.append("CMD_LLM_PROVIDER must be 'openai' or 'gemini'")
        else:
            providers_needed.add(cmd_provider_name)

    for provider in providers_needed:
        if provider == 'openai':
            if not os.getenv('OPENAI_API_KEY'):
                missing.append('OPENAI_API_KEY (required for OpenAI provider)')
            if not os.getenv('OPENAI_MODEL'):
                missing.append('OPENAI_MODEL (required for OpenAI provider)')
        elif provider == 'gemini':
            if not os.getenv('GOOGLE_API_KEY'):
                missing.append('GOOGLE_API_KEY (required for Gemini provider)')
            if not os.getenv('GEMINI_MODEL'):
                missing.append('GEMINI_MODEL (required for Gemini provider)')

    cmd_max_tokens = os.getenv('CMD_MAX_COMPLETION_TOKENS', '').strip()
    if cmd_max_tokens:
        try:
            if int(cmd_max_tokens) <= 0:
                missing.append('CMD_MAX_COMPLETION_TOKENS must be a positive integer')
        except ValueError:
            missing.append('CMD_MAX_COMPLETION_TOKENS must be a positive integer')

    if missing:
        print("ERROR: Missing required configuration:", file=sys.stderr)
        for var in missing:
            print(f"  - {var}", file=sys.stderr)
        print("\nCopy mush_gpt.env.example to mush_gpt.env and configure all required values.", file=sys.stderr)
        sys.exit(1)


# Validate config before proceeding
validate_config()

app = Flask(__name__)

def setup_logging():
    """Setup logging configuration with file size limits"""
    logger = logging.getLogger('mush_gpt')
    log_level = os.getenv('LOG_LEVEL').upper()
    logger.setLevel(getattr(logging, log_level))

    logger.handlers.clear()

    max_bytes = int(os.getenv('LOG_MAX_SIZE'))
    backup_count = int(os.getenv('LOG_BACKUP_COUNT'))

    file_handler = RotatingFileHandler(
        'mush_gpt.log',
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(getattr(logging, log_level))

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger

logger = setup_logging()

# Initialize default LLM provider (OpenAI or Gemini based on LLM_PROVIDER env var)
try:
    default_provider = get_provider()
    logger.info(f"Default LLM Provider: {default_provider.provider_name}")
except Exception as e:
    logger.error(f"Failed to initialize LLM provider: {e}")
    default_provider = None


def resolve_provider(provider_override=None):
    """
    Get the appropriate LLM provider for a request.
    
    Args:
        provider_override: Optional provider name ('openai' or 'gemini') to use
                          instead of the default.
    
    Returns:
        The provider instance to use, or None if unavailable.
    """
    if not provider_override:
        return default_provider
    
    # Validate override value
    provider_override = provider_override.lower().strip()
    if provider_override not in ('openai', 'gemini'):
        logger.warning(f"Invalid provider override '{provider_override}', using default")
        return default_provider
    
    # Return default if it matches the override
    if default_provider and default_provider.provider_name == provider_override:
        return default_provider
    
    # Get a different provider
    try:
        return get_provider(provider_name=provider_override, force_new=True)
    except Exception as e:
        logger.error(f"Failed to get provider '{provider_override}': {e}")
        return default_provider


def resolve_cmd_provider(json_provider_override=None):
    """
    Get the LLM provider for /cmd requests.

    Precedence: JSON provider (if sent) > CMD_LLM_PROVIDER > LLM_PROVIDER default.
    """
    override = (json_provider_override or '').strip().lower() or None
    if not override:
        override = _cmd_llm_provider
    return resolve_provider(override)


auth_key = os.getenv("AUTH_KEY")

max_input_length = int(os.getenv('MAX_INPUT_LENGTH'))
max_completion_tokens = int(os.getenv('MAX_COMPLETION_TOKENS'))

# /cmd endpoint settings (optional; fall back to LLM_PROVIDER / MAX_COMPLETION_TOKENS)
_cmd_llm_provider = os.getenv('CMD_LLM_PROVIDER', '').strip().lower() or None
_cmd_max_env = os.getenv('CMD_MAX_COMPLETION_TOKENS', '').strip()
cmd_max_completion_tokens = (
    int(_cmd_max_env) if _cmd_max_env else max_completion_tokens
)

if _cmd_llm_provider:
    logger.info(f"/cmd LLM provider: {_cmd_llm_provider}")
else:
    logger.info("/cmd LLM provider: using LLM_PROVIDER default")
logger.info(f"/cmd max completion tokens: {cmd_max_completion_tokens}")

# Characters that don't maintain conversation history (stateless)
# Configured via STATELESS_CHARACTERS env var (comma-separated, case-insensitive)
_stateless_characters = set(
    x.strip().lower() for x in os.getenv('STATELESS_CHARACTERS', '').split(',') if x.strip()
)
if _stateless_characters:
    logger.info(f"Stateless characters configured: {_stateless_characters}")

character_buffers = {}

def secure_sanitize_message(message):
    """
    Centralized secure sanitization function for LLM responses.
    Designed to be safe for MUSH public channels while preserving readability.
    """
    if not isinstance(message, str):
        return ""

    # Apply unicode replacements first so all transformations work on normalized text
    unicode_replacements = {
        '\u2013': '-',
        '\u2014': '--',
        '\u2012': '-',
        '\u2015': '--',
        '\u2043': '-',
        '\u2212': '-',

        '\u2018': "'",
        '\u2019': "'",
        '\u201a': "'",
        '\u201b': "'",
        '\u201c': '"',
        '\u201d': '"',
        '\u201e': '"',
        '\u201f': '"',

        '\u2026': '...',
        '\u2022': '*',
        '\u2023': '>',
        '\u2024': '.',
        '\u2025': '..',
        '\u2032': "'",
        '\u2033': '"',
        '\u2039': '<',
        '\u203a': '>',
        '\u2044': '/',
        '\u2045': '[',
        '\u2046': ']',

        '\u00b0': 'deg',
        '\u00b1': '+/-',
        '\u00b2': '^2',
        '\u00b3': '^3',
        '\u00b4': "'",
        '\u00b5': 'u',
        '\u00b6': 'P',
        '\u00b7': '*',
        '\u00b8': ',',
        '\u00b9': '^1',
        '\u00ba': 'o',
        '\u00bb': '>>',
        '\u00bc': '1/4',
        '\u00bd': '1/2',
        '\u00be': '3/4',

        '\u00a2': 'c',
        '\u00a3': 'L',
        '\u00a5': 'Y',
        '\u00a9': '(c)',
        '\u00ae': '(R)',
        '\u2122': '(TM)',

        '\u2017': '__',
        '\u2010': '-',
        '\u2011': '-',

        '\u00a0': ' ',
        '\u2000': ' ',
        '\u2001': ' ',
        '\u2002': ' ',
        '\u2003': ' ',
        '\u2004': ' ',
        '\u2005': ' ',
        '\u2006': ' ',
        '\u2007': ' ',
        '\u2008': ' ',
        '\u2009': ' ',
        '\u200a': ' ',
        '\u200b': '',
        '\u200c': '',
        '\u200d': '',
        '\u2028': '\n',
        '\u2029': '\n\n',
        '\u202f': ' ',
        '\u205f': ' ',
        '\u3000': ' ',

        '\u00a1': '!',
        '\u00bf': '?',
        '\u00d7': 'x',
        '\u00f7': '/',
        '\u00a7': 'S',
        '\u2260': '!=',
        '\u2264': '<=',
        '\u2265': '>=',
        '\u2192': '->',
        '\u2190': '<-',
        '\u2191': '^',
        '\u2193': 'v',
    }

    for unicode_char, ascii_char in unicode_replacements.items():
        message = message.replace(unicode_char, ascii_char)

    message = message.replace('[', '')     # Remove left brackets (MUSH commands)
    message = message.replace(']', '')     # Remove right brackets (MUSH commands)
    # Literal %r/%%r (e.g. echoed from conversation history) → newline before stripping other % codes
    message = re.sub(r'%%r|%r|%R', '\n', message)
    message = message.replace('%', '')     # Remove remaining percent signs (MUSH functions)

    dangerous_control_chars = [
        '\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07',
        '\x08', '\x0b', '\x0c', '\x0e', '\x0f', '\x10', '\x11', '\x12', '\x13', '\x14',
        '\x15', '\x16', '\x17', '\x18', '\x19', '\x1a', '\x1b', '\x1c', '\x1d', '\x1e', '\x1f'
    ]

    for char in dangerous_control_chars:
        message = message.replace(char, '')

    message = message.replace('&', 'and')

    # Handle line breaks - convert to MUSH %r format
    message = message.replace('\\n', '\n')
    message = message.replace('\\r', '\r')
    message = message.replace('\r\n', '\n')
    message = message.replace('\r', '\n')
    message = re.sub(r'[ \t]+', ' ', message)  # Normalize spaces/tabs
    message = re.sub(r'\n\s*\n\s*\n+', '\n\n', message)  # Limit consecutive line breaks
    message = message.replace('\n', '%r')  # Convert to MUSH line breaks

    # Apply length limit and truncation
    max_length = max_input_length
    if len(message) > max_length:
        message = message[:max_length]
        message += "... [truncated]"

    message = message.strip()

    return message

@app.route('/cmd', methods=['POST'])
def cmd():
    try:
        json_data = request.get_json()
        if not json_data or 'auth' not in json_data or 'char' not in json_data:
            return jsonify({"message": "Failed: Invalid request data"}), 400

        auth = json_data['auth'].strip()
        char = json_data['char'].strip()
        prompt_file = json_data.get('prompt_file', '').strip() or None
        provider_override = json_data.get('provider', '').strip() or None

        if len(auth) > 100 or len(char) > 100:
            return jsonify({"message": "Failed: Invalid input length"}), 400

        if auth != auth_key:
            return jsonify({"message": "Failed: Unauthorized"}), 401

        # Validate character exists in the specified (or default) prompt file
        valid_chars = get_valid_prompts(prompt_file)
        if char not in valid_chars:
            return jsonify({"message": f"Failed: Invalid character reference '{char}'. Valid: {valid_chars}"}), 400

        active_provider = resolve_cmd_provider(provider_override)
        if active_provider is None:
            return jsonify({"message": "Failed: LLM provider not initialized"}), 500

        logger.debug(
            "/cmd request char=%s provider=%s max_tokens=%d",
            char, active_provider.provider_name, cmd_max_completion_tokens
        )

        # Use provider abstraction
        result = active_provider.complete(
            messages=[],
            system_prompt=get_prompt(char, prompt_file),
            temperature=1.0,
            max_tokens=cmd_max_completion_tokens
        )

        if result.finish_reason == FinishReason.CONTENT_FILTER:
            return jsonify({"message": "Failed: Content filter activated"})
        elif result.finish_reason == FinishReason.LENGTH:
            return jsonify({"message": "Failed: Output exceeds maximum length"})
        elif result.finish_reason == FinishReason.ERROR:
            logger.error(f"Provider error: {result.error}")
            return jsonify({"message": "Failed: Provider error"}), 500
        else:
            sanitized_content = secure_sanitize_message(result.content)
            logger.debug(
                "/cmd response char=%s chars=%d",
                char, len(sanitized_content)
            )
            return jsonify({"message": sanitized_content})

    except Exception as e:
        logger.error(f"Error in /cmd endpoint: {str(e)}")
        return jsonify({"message": "Failed: Error"}), 500

@app.route('/bot', methods=['POST'])
def bot():
    try:
        json_data = request.get_json()
        if not json_data or 'text' not in json_data or 'auth' not in json_data or 'char' not in json_data:
            return jsonify({"message": "Failed: Invalid request data"}), 400

        text = json_data['text'].strip()
        auth = json_data['auth'].strip()
        char = json_data['char'].strip()
        context_only = json_data.get('context_only', False)
        prompt_file = json_data.get('prompt_file', '').strip() or None
        provider_override = json_data.get('provider', '').strip() or None
        # Allow passing system_prompt directly (used by bots with their own prompt files)
        direct_system_prompt = json_data.get('system_prompt', '').strip() or None

        if len(auth) > 100 or len(char) > 100:
            return jsonify({"message": "Failed: Invalid input length"}), 400

        if len(text) > max_input_length:
            return jsonify({"message": "Failed: Input exceeds maximum length"}), 400

        # Limit system_prompt size to prevent abuse (50KB max)
        if direct_system_prompt and len(direct_system_prompt) > 50000:
            return jsonify({"message": "Failed: System prompt exceeds maximum length"}), 400

        if auth != auth_key:
            return jsonify({"message": "Failed: Unauthorized"}), 401

        # Determine system prompt: use direct prompt if provided, otherwise lookup by char
        if direct_system_prompt:
            system_prompt = direct_system_prompt
        else:
            # Validate character exists in the specified (or default) prompt file
            valid_chars = get_valid_prompts(prompt_file)
            if char not in valid_chars:
                return jsonify({"message": f"Failed: Invalid character reference '{char}'. Valid: {valid_chars}"}), 400
            system_prompt = get_prompt(char, prompt_file)

        add_message("user", text, char)

        if context_only:
            return jsonify({"message": "Context added"})

        # Get the appropriate provider
        active_provider = resolve_provider(provider_override)
        if active_provider is None:
            return jsonify({"message": "Failed: LLM provider not initialized"}), 500

        char_messages = get_char_messages(char)

        logger.debug(
            "/bot request char=%s text=%r history_len=%d",
            char, text, len(char_messages)
        )

        # Use provider abstraction
        result = active_provider.complete(
            messages=char_messages,
            system_prompt=system_prompt,
            temperature=1.0,
            max_tokens=max_completion_tokens
        )

        if result.finish_reason == FinishReason.CONTENT_FILTER:
            return jsonify({"message": "Failed: Content filter activated"})
        elif result.finish_reason == FinishReason.LENGTH:
            return jsonify({"message": "Failed: Output exceeds maximum length"})
        elif result.finish_reason == FinishReason.ERROR:
            logger.error(f"Provider error: {result.error}")
            return jsonify({"message": "Failed: Provider error"}), 500
        else:
            sanitized_content = secure_sanitize_message(result.content)
            logger.debug(
                "/bot response char=%s raw=%r sanitized=%r",
                char, result.content, sanitized_content
            )
            add_message("assistant", sanitized_content, char)
            return jsonify({"message": sanitized_content})

    except Exception as e:
        logger.error(f"Error in /bot endpoint: {str(e)}")
        return jsonify({"message": "Failed: Error"}), 500

@app.route('/adhoc', methods=['POST'])
def adhoc():
    """Ad-hoc endpoint for special requests like relevance analysis"""
    try:
        json_data = request.get_json()
        if not json_data or 'text' not in json_data or 'auth' not in json_data or 'char' not in json_data:
            return jsonify({"message": "Failed: Invalid request data"}), 400

        text = json_data['text'].strip()
        auth = json_data['auth'].strip()
        char = json_data['char'].strip()
        prompt_file = json_data.get('prompt_file', '').strip() or None
        provider_override = json_data.get('provider', '').strip() or None
        # Allow passing system_prompt directly (used by bots with their own prompt files)
        direct_system_prompt = json_data.get('system_prompt', '').strip() or None

        if len(auth) > 100 or len(char) > 100:
            return jsonify({"message": "Failed: Invalid input length"}), 400

        if len(text) > max_input_length:
            return jsonify({"message": "Failed: Input exceeds maximum length"}), 400

        # Limit system_prompt size to prevent abuse (50KB max)
        if direct_system_prompt and len(direct_system_prompt) > 50000:
            return jsonify({"message": "Failed: System prompt exceeds maximum length"}), 400

        if auth != auth_key:
            return jsonify({"message": "Failed: Unauthorized"}), 401

        # Get the appropriate provider
        active_provider = resolve_provider(provider_override)
        if active_provider is None:
            return jsonify({"message": "Failed: LLM provider not initialized"}), 500

        # Determine system prompt: use direct prompt if provided, otherwise lookup by char
        if direct_system_prompt:
            system_prompt = direct_system_prompt
        else:
            # Validate character exists in the specified (or default) prompt file
            valid_chars = get_valid_prompts(prompt_file)
            if char not in valid_chars:
                return jsonify({"message": f"Failed: Invalid character reference '{char}'. Valid: {valid_chars}"}), 400
            system_prompt = get_character_context_interests(char, prompt_file)

        # Use provider abstraction
        result = active_provider.complete(
            messages=[{"role": "user", "content": text}],
            system_prompt=system_prompt,
            temperature=1.0,
            max_tokens=max_completion_tokens
        )

        if result.finish_reason == FinishReason.CONTENT_FILTER:
            return jsonify({"message": "Failed: Content filter activated"})
        elif result.finish_reason == FinishReason.LENGTH:
            return jsonify({"message": "Failed: Output exceeds maximum length"})
        elif result.finish_reason == FinishReason.ERROR:
            logger.error(f"Provider error: {result.error}")
            return jsonify({"message": "Failed: Provider error"}), 500
        else:
            return jsonify({"message": secure_sanitize_message(result.content)})

    except Exception as e:
        logger.error(f"Error in /adhoc endpoint: {str(e)}")
        return jsonify({"message": "Failed: Error"}), 500

def add_message(role, content, character):
    global character_buffers

    # Skip conversation history for stateless characters
    if character.lower() in _stateless_characters:
        return

    if character not in character_buffers:
        character_buffers[character] = []

    character_buffers[character].append({
        "role": role,
        "content": content,
        "timestamp": time.time()
    })

    character_buffers[character] = character_buffers[character][-50:]

    current_time = time.time()
    character_buffers[character] = [
        msg for msg in character_buffers[character]
        if current_time - msg["timestamp"] < 3600
    ]

def get_char_messages(character):
    # Stateless characters have no conversation history
    if character.lower() in _stateless_characters:
        return []

    if character not in character_buffers:
        return []

    return [
        {"role": msg["role"], "content": msg["content"]}
        for msg in character_buffers[character]
    ]



if __name__ == '__main__':
    host = os.getenv('FLASK_HOST')
    port = int(os.getenv('FLASK_PORT'))
    debug = os.getenv('FLASK_DEBUG').lower() == 'true'

    print(f"Starting MUSH GPT API server on {host}:{port}")
    print(f"Debug mode: {debug}")
    print(f"LLM Provider: {default_provider.provider_name if default_provider else 'NOT INITIALIZED'}")
    cmd_provider_label = _cmd_llm_provider or (
        default_provider.provider_name if default_provider else 'NOT INITIALIZED'
    )
    print(f"/cmd LLM Provider: {cmd_provider_label}")
    print(f"/cmd max completion tokens: {cmd_max_completion_tokens}")
    print(f"Default characters: {', '.join(get_valid_prompts())}")

    app.run(host=host, port=port, debug=debug, threaded=True)
