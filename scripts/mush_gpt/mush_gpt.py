# MIT License
# Copyright (c) 2023 Matt Westfall (@disloops)

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
__version__ = '0.3'
__email__ = 'disloops@gmail.com'


from flask import Flask, request, jsonify
from openai import OpenAI
import time
import os
import sys
import json
import re
import unicodedata
import logging
from logging.handlers import RotatingFileHandler
from prompts import get_prompt, get_valid_prompts, get_character_context_interests

def load_env_file(filepath):
    """Load environment variables from a .env file"""
    env_vars = {}
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    return env_vars

env_vars = load_env_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mush_gpt.env'))
for key, value in env_vars.items():
    os.environ[key] = value

app = Flask(__name__)

def setup_logging():
    """Setup logging configuration with file size limits"""
    logger = logging.getLogger('mush_gpt')
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    logger.handlers.clear()

    max_bytes = int(os.getenv('LOG_MAX_SIZE', '10485760'))
    backup_count = int(os.getenv('LOG_BACKUP_COUNT', '3'))

    file_handler = RotatingFileHandler(
        'mush_gpt.log',
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(getattr(logging, log_level, logging.INFO))

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger

logger = setup_logging()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

auth_key = os.getenv("AUTH_KEY")

prompts = get_valid_prompts()

model = os.getenv('OPENAI_MODEL', 'gpt-5')

max_input_length = int(os.getenv('MAX_INPUT_LENGTH', '10000'))
max_completion_tokens = int(os.getenv('MAX_COMPLETION_TOKENS', '10000'))

character_buffers = {}



def secure_sanitize_message(message, character=None, endpoint=None):
    """
    Centralized secure sanitization function for ChatGPT responses.
    Designed to be safe for MUSH public channels while preserving readability.
    """
    if not isinstance(message, str):
        return ""

    if endpoint != '/cmd':
        message = message.replace('%r', ' ')  # Convert %r to spaces for /bot endpoint

    message = message.replace('[', '')     # Remove left brackets (MUSH commands)
    message = message.replace(']', '')     # Remove right brackets (MUSH commands)
    message = message.replace('%', '')     # Remove percent signs (MUSH functions)

    dangerous_control_chars = [
        '\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07',
        '\x08', '\x0b', '\x0c', '\x0e', '\x0f', '\x10', '\x11', '\x12', '\x13', '\x14',
        '\x15', '\x16', '\x17', '\x18', '\x19', '\x1a', '\x1b', '\x1c', '\x1d', '\x1e', '\x1f'
    ]

    for char in dangerous_control_chars:
        message = message.replace(char, '')

    message = message.replace('&', 'and')
    message = message.replace('\\n', ' ')
    message = message.replace('\\r', ' ')
    message = message.replace('\n', ' ')
    message = message.replace('\r', ' ')

    import re
    message = re.sub(r'\s+', ' ', message)  # Replace multiple whitespace with single space

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
        '\u00b0': 'deg',
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
        '\u00b6': 'P',
        '\u00a7': 'S',
        '\u00b1': '+/-',
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

    max_length = max_input_length
    if len(message) > max_length:
        message = message[:max_length]
        message += "... [truncated]"

    message = message.strip()

    return message

def sanitize_input(text, character=None):
    """Legacy function - use secure_sanitize_message instead"""
    return secure_sanitize_message(text, character)

@app.route('/cmd', methods=['POST'])
def cmd():
    try:
        json_data = request.get_json()
        if not json_data or 'auth' not in json_data or 'char' not in json_data:
            return jsonify({"message": "Failed: Invalid request data"}), 400

        auth = json_data['auth'].strip()
        char = json_data['char'].strip()

        if len(auth) > 100 or len(char) > 100:
            return jsonify({"message": "Failed: Invalid input length"}), 400

        if len(auth) > 100 or auth != auth_key:
            return jsonify({"message": "Failed: Unauthorized"}), 401

        if len(char) > 100 or char not in prompts:
            return jsonify({"message": "Failed: Invalid character reference"}), 400

        response = client.chat.completions.create(
            model=model,
            max_completion_tokens=max_completion_tokens,
            temperature=1,
            top_p=1,
            messages=[
                {"role": "system", "content": get_prompt(char)}
            ]
        )

        finish_reason = response.choices[0].finish_reason

        if finish_reason == 'content_filter':
            return jsonify({"message": "Failed: Content filter activated"})
        elif finish_reason == 'length':
            return jsonify({"message": "Failed: Output exceeds maximum length"})
        else:
            message_content = response.choices[0].message.content
            sanitized_content = secure_sanitize_message(message_content, char, '/cmd')
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

        if len(auth) > 100 or len(char) > 100:
            return jsonify({"message": "Failed: Invalid input length"}), 400
        max_length = max_input_length
        if len(text) > max_length:
            return jsonify({"message": "Failed: Input exceeds maximum length"}), 400

        if len(auth) > 100 or auth != auth_key:
            return jsonify({"message": "Failed: Unauthorized"}), 401

        max_length = max_input_length
        if len(text) > max_length:
            return jsonify({"message": "Failed: Input exceeds maximum length"}), 400

        if len(char) > 100 or char not in prompts:
            return jsonify({"message": "Failed: Invalid character reference"}), 400

        add_message("user", text, char)

        if context_only:
            return jsonify({"message": "Context added"})

        char_messages = get_char_messages(char)

        response = client.chat.completions.create(
            model=model,
            max_completion_tokens=max_completion_tokens,
            temperature=1,
            top_p=1,
            messages=[
                {"role": "system", "content": get_prompt(char)},
                *char_messages
            ]
        )

        finish_reason = response.choices[0].finish_reason

        if finish_reason == 'content_filter':
            return jsonify({"message": "Failed: Content filter activated"})
        elif finish_reason == 'length':
            return jsonify({"message": "Failed: Output exceeds maximum length"})
        else:
            message_content = response.choices[0].message.content
            sanitized_content = secure_sanitize_message(message_content, char, '/bot')
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

        if len(auth) > 100 or len(char) > 100:
            return jsonify({"message": "Failed: Invalid input length"}), 400
        max_length = max_input_length
        if len(text) > max_length:
            return jsonify({"message": "Failed: Input exceeds maximum length"}), 400

        if len(auth) > 100 or auth != auth_key:
            return jsonify({"message": "Failed: Unauthorized"}), 401

        max_length = max_input_length
        if len(text) > max_length:
            return jsonify({"message": "Failed: Input exceeds maximum length"}), 400

        system_prompt = get_character_context_interests(char)

        response = client.chat.completions.create(
            model=model,
            max_completion_tokens=max_completion_tokens,
            temperature=1,
            top_p=1,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
        )

        finish_reason = response.choices[0].finish_reason

        if finish_reason == 'content_filter':
            return jsonify({"message": "Failed: Content filter activated"})
        elif finish_reason == 'length':
            return jsonify({"message": "Failed: Output exceeds maximum length"})
        else:
            message_content = response.choices[0].message.content
            return jsonify({"message": secure_sanitize_message(message_content, char, '/adhoc')})

    except Exception as e:
        logger.error(f"Error in /adhoc endpoint: {str(e)}")
        return jsonify({"message": "Failed: Error"}), 500

def add_message(role, content, character):
    global character_buffers

    if character == "today":
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
    if character == "today":
        return []

    if character not in character_buffers:
        return []

    return [
        {"role": msg["role"], "content": msg["content"]}
        for msg in character_buffers[character]
    ]



if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', '5000'))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    print(f"Starting MUSH GPT API server on {host}:{port}")
    print(f"Debug mode: {debug}")
    print(f"Model: {model}")
    print(f"Valid characters: {', '.join(prompts)}")

    app.run(host=host, port=port, debug=debug)
