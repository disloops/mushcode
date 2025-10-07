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

# This script functions as a localhost server that a MUSH can use to easily
# interact with the OpenAI API.
#
# ENDPOINT STRUCTURE:
# - /bot - Persistent bot-style characters with memory (oracle, daemon, ptolemy, starlink)
# - /cmd - One-time command-style interactions (today, ptolemy, etc.)
#
# ASTRONOMICAL DATA INTEGRATION:
# - Fetches real astronomical data from NASA's JPL Horizons API
# - Provides accurate moon phases, planetary positions, and zodiac signs
# - Automatically embeds astronomical data into "ptolemy" and "today" bot prompts
# - Uses NASA's official ephemeris data for reliability and accuracy
# - No API keys required for NASA data (free and official)

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

# Load environment variables
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

# Load configuration from .env file
env_vars = load_env_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mush_gpt.env'))
for key, value in env_vars.items():
    os.environ[key] = value

app = Flask(__name__)

# Setup logging with size limits
def setup_logging():
    """Setup logging configuration with file size limits"""
    logger = logging.getLogger('mush_gpt')
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Clear any existing handlers
    logger.handlers.clear()

    # Get log settings from environment
    max_bytes = int(os.getenv('LOG_MAX_SIZE', '10485760'))  # 10MB default
    backup_count = int(os.getenv('LOG_BACKUP_COUNT', '3'))

    # Create rotating file handler
    file_handler = RotatingFileHandler(
        'mush_gpt.log',
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(getattr(logging, log_level, logging.INFO))

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(file_handler)

    return logger

# Initialize logger
logger = setup_logging()

# OpenAI API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Pseudo-secret password value that must be present in incoming requests
auth_key = os.getenv("AUTH_KEY")

# Valid MUSH cases for which a system pre-prompt exists (dynamically loaded)
prompts = get_valid_prompts()

# Model (may depend on the prompt scenario)
model = os.getenv('OPENAI_MODEL', 'gpt-4o')

# Character-specific message buffers
character_buffers = {}

# CENTRALIZED SECURITY MODULE
# All bots and commands should use these functions instead of implementing their own

def validate_input(text, max_length=None):
    if max_length is None:
        max_length = int(os.getenv('MAX_INPUT_LENGTH', '10000'))
    """Validate input text for security - designed for ChatGPT responses"""
    if not isinstance(text, str):
        return False
    if len(text) > max_length:
        return False
    # Check only for the most dangerous patterns that could cause MUSH code execution
    dangerous_patterns = [
        r'\[.*\]',     # MUSH commands in brackets
        r'#.*',         # MUSH comments
        r'%.*',         # MUSH functions
        r'[\x00-\x08\x0b\x0c\x0e-\x1f]'  # Only the most dangerous control characters
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, text):
            return False
    return True

def secure_sanitize_message(message, character=None, endpoint=None):
    """
    Centralized secure sanitization function for ChatGPT responses.
    Designed to be safe for MUSH public channels while preserving readability.
    """
    if not isinstance(message, str):
        return ""

    # Handle line breaks - preserve %r for /cmd endpoint, convert to spaces for /bot
    if endpoint != '/cmd':
        message = message.replace('%r', ' ')  # Convert %r to spaces for /bot endpoint

    # Remove only MUSH-specific dangerous characters that could cause code execution
    # Keep normal punctuation that's safe in public channels
    message = message.replace('[', '')     # Remove left brackets (MUSH commands)
    message = message.replace(']', '')     # Remove right brackets (MUSH commands)
    # Hash symbols are now preserved for location messages
    message = message.replace('%', '')     # Remove percent signs (MUSH functions)

    # Remove only the most dangerous control characters, keep normal ones
    dangerous_control_chars = [
        '\x00', '\x01', '\x02', '\x03', '\x04', '\x05', '\x06', '\x07',  # Null and control
        '\x08', '\x0b', '\x0c', '\x0e', '\x0f', '\x10', '\x11', '\x12', '\x13', '\x14',
        '\x15', '\x16', '\x17', '\x18', '\x19', '\x1a', '\x1b', '\x1c', '\x1d', '\x1e', '\x1f'
    ]

    for char in dangerous_control_chars:
        message = message.replace(char, '')

    # Safe replacements for readability
    message = message.replace('&', 'and')  # Replace ampersands
    message = message.replace('\\n', ' ') # Convert literal \n to spaces
    message = message.replace('\\r', ' ') # Convert literal \r to spaces
    message = message.replace('\n', ' ')  # Convert actual newlines to spaces
    message = message.replace('\r', ' ')  # Convert actual carriage returns to spaces

    # Clean up multiple consecutive spaces
    import re
    message = re.sub(r'\s+', ' ', message)  # Replace multiple whitespace with single space

    # Convert Unicode characters to ASCII equivalents for MUSH compatibility
    unicode_replacements = {
        # Dashes and hyphens
        '\u2013': '-',  # en dash
        '\u2014': '--', # em dash
        '\u2012': '-',  # figure dash
        '\u2015': '--', # horizontal bar
        '\u2043': '-',  # bullet operator
        '\u2212': '-',  # minus sign

        # Quotes
        '\u2018': "'",  # left single quote
        '\u2019': "'",  # right single quote
        '\u201a': "'",  # single low quote
        '\u201b': "'",  # single high quote
        '\u201c': '"',  # left double quote
        '\u201d': '"',  # right double quote
        '\u201e': '"',  # double low quote
        '\u201f': '"',  # right double quote

        # Other punctuation
        '\u2026': '...', # ellipsis
        '\u2022': '*',   # bullet point
        '\u2023': '>',   # triangular bullet
        '\u2024': '.',   # one dot leader
        '\u2025': '..',  # two dot leader
        '\u2032': "'",   # prime
        '\u2033': '"',   # double prime
        '\u2039': '<',   # single left-pointing angle quote
        '\u203a': '>',   # single right-pointing angle quote
        '\u2044': '/',   # fraction slash
        '\u2045': '[',   # left square bracket with quill
        '\u2046': ']',   # right square bracket with quill

        # Mathematical and technical
        '\u00b0': 'deg', # degree sign
        '\u00b1': '+/-', # plus-minus sign
        '\u00b2': '^2',  # superscript two
        '\u00b3': '^3',  # superscript three
        '\u00b4': "'",   # acute accent
        '\u00b5': 'u',   # micro sign
        '\u00b6': 'P',   # pilcrow sign
        '\u00b7': '*',   # middle dot
        '\u00b8': ',',   # cedilla
        '\u00b9': '^1',  # superscript one
        '\u00ba': 'o',   # masculine ordinal indicator
        '\u00bb': '>>',   # right-pointing double angle quote
        '\u00bc': '1/4', # vulgar fraction one quarter
        '\u00bd': '1/2', # vulgar fraction one half
        '\u00be': '3/4', # vulgar fraction three quarters

        # Currency and symbols
        '\u00a2': 'c',   # cent sign
        '\u00a3': 'L',   # pound sign
        '\u00a5': 'Y',   # yen sign
        '\u00a9': '(c)', # copyright sign
        '\u00ae': '(R)', # registered sign
        '\u00b0': 'deg', # degree sign
        '\u2122': '(TM)', # trade mark sign

        # Underscores and lines
        '\u2017': '__', # double underscore
        '\u2010': '-',  # hyphen
        '\u2011': '-',  # non-breaking hyphen

        # Spaces and whitespace
        '\u00a0': ' ',  # non-breaking space
        '\u2000': ' ',  # en quad
        '\u2001': ' ',  # em quad
        '\u2002': ' ',  # en space
        '\u2003': ' ',  # em space
        '\u2004': ' ',  # three-per-em space
        '\u2005': ' ',  # four-per-em space
        '\u2006': ' ',  # six-per-em space
        '\u2007': ' ',  # figure space
        '\u2008': ' ',  # punctuation space
        '\u2009': ' ',  # thin space
        '\u200a': ' ',  # hair space
        '\u200b': '',   # zero width space
        '\u200c': '',   # zero width non-joiner
        '\u200d': '',   # zero width joiner
        '\u2028': '\n', # line separator
        '\u2029': '\n\n', # paragraph separator
        '\u202f': ' ',  # narrow no-break space
        '\u205f': ' ',  # medium mathematical space
        '\u3000': ' ',  # ideographic space

        # Additional common characters
        '\u00a1': '!',  # inverted exclamation mark
        '\u00bf': '?',  # inverted question mark
        '\u00d7': 'x',  # multiplication sign
        '\u00f7': '/',  # division sign
        '\u00b6': 'P',  # pilcrow sign (paragraph)
        '\u00a7': 'S',  # section sign
        '\u00b1': '+/-', # plus-minus sign
        '\u2260': '!=', # not equal to
        '\u2264': '<=', # less than or equal to
        '\u2265': '>=', # greater than or equal to
        '\u2192': '->', # rightwards arrow
        '\u2190': '<-', # leftwards arrow
        '\u2191': '^',  # upwards arrow
        '\u2193': 'v',  # downwards arrow
    }

    for unicode_char, ascii_char in unicode_replacements.items():
        message = message.replace(unicode_char, ascii_char)

    # Limit message length to prevent buffer overflow
    max_length = int(os.getenv('MAX_INPUT_LENGTH', '5000'))
    if len(message) > max_length:
        message = message[:max_length]
        message += "... [truncated]"

    # Strip any remaining whitespace but preserve newlines
    message = message.strip()

    return message

def sanitize_input(text, character=None):
    """Legacy function - use secure_sanitize_message instead"""
    return secure_sanitize_message(text, character)

@app.route('/cmd', methods=['POST'])
def cmd():
    try:
        # Check for POST parameters
        json_data = request.get_json()
        if not json_data or 'auth' not in json_data or 'char' not in json_data:
            return jsonify({"message": "Failed: Invalid request data"}), 400

        auth = json_data['auth'].strip()
        char = json_data['char'].strip()

        # SECURITY: Validate inputs
        if not validate_input(auth, 100):
            return jsonify({"message": "Failed: Invalid auth input"}), 400
        if not validate_input(char, 100):
            return jsonify({"message": "Failed: Invalid character input"}), 400

        if len(auth) > 100 or auth != auth_key:
            return jsonify({"message": "Failed: Unauthorized"}), 401

        if len(char) > 100 or char not in prompts:
            return jsonify({"message": "Failed: Invalid character reference"}), 400

        # Format request to OpenAI API endpoint
        response = client.chat.completions.create(
            model=model,
            max_tokens=2000,
            temperature=1,
            top_p=1,
            frequency_penalty=1,
            presence_penalty=1,
            messages=[
                {"role": "system", "content": get_prompt(char)}
            ]
        )

        # Return response to caller
        finish_reason = response.choices[0].finish_reason

        if finish_reason == 'content_filter':
            return jsonify({"message": "Failed: Content filter activated"})
        elif finish_reason == 'length':
            return jsonify({"message": "Failed: Output exceeds maximum length"})
        else:
            message_content = response.choices[0].message.content
            # Sanitize based on character type - preserve %r for /cmd endpoint
            sanitized_content = secure_sanitize_message(message_content, char, '/cmd')
            return jsonify({"message": sanitized_content})

    except Exception as e:
        logger.error(f"Error in /cmd endpoint: {str(e)}")
        return jsonify({"message": "Failed: Error"}), 500

@app.route('/bot', methods=['POST'])
def bot():
    try:

        # Check for POST parameters
        json_data = request.get_json()
        if not json_data or 'text' not in json_data or 'auth' not in json_data or 'char' not in json_data:
            return jsonify({"message": "Failed: Invalid request data"}), 400

        text = json_data['text'].strip()
        auth = json_data['auth'].strip()
        char = json_data['char'].strip()
        context_only = json_data.get('context_only', False)  # Optional: just add to buffer, don't call LLM

        # SECURITY: Validate inputs
        if not validate_input(auth, 100):
            return jsonify({"message": "Failed: Invalid auth input"}), 400
        if not validate_input(char, 100):
            return jsonify({"message": "Failed: Invalid character input"}), 400
        if not validate_input(text):
            return jsonify({"message": "Failed: Invalid text input"}), 400

        if len(auth) > 100 or auth != auth_key:
            return jsonify({"message": "Failed: Unauthorized"}), 401

        max_length = int(os.getenv('MAX_INPUT_LENGTH', '10000'))
        if len(text) > max_length:
            return jsonify({"message": "Failed: Input exceeds maximum length"}), 400

        if len(char) > 100 or char not in prompts:
            return jsonify({"message": "Failed: Invalid character reference"}), 400

        # Add user message to the buffer
        add_message("user", text, char)

        # If context_only is True, just add to buffer and return success
        if context_only:
            return jsonify({"message": "Context added"})

        # Filter messages for the current character
        char_messages = get_char_messages(char)

        # Format request to OpenAI API endpoint
        response = client.chat.completions.create(
            model=model,
            max_tokens=2000,
            temperature=1,
            top_p=1,
            frequency_penalty=1,
            presence_penalty=1,
            messages=[
                {"role": "system", "content": get_prompt(char)},
                *char_messages
            ]
        )

        # Return response to caller
        finish_reason = response.choices[0].finish_reason

        if finish_reason == 'content_filter':
            return jsonify({"message": "Failed: Content filter activated"})
        elif finish_reason == 'length':
            return jsonify({"message": "Failed: Output exceeds maximum length"})
        else:
            message_content = response.choices[0].message.content
            # Sanitize based on character type - convert %r to spaces for /bot endpoint
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
        # Check for POST parameters
        json_data = request.get_json()
        if not json_data or 'text' not in json_data or 'auth' not in json_data or 'char' not in json_data:
            return jsonify({"message": "Failed: Invalid request data"}), 400

        text = json_data['text'].strip()
        auth = json_data['auth'].strip()
        char = json_data['char'].strip()

        # SECURITY: Validate inputs
        if not validate_input(auth, 100):
            return jsonify({"message": "Failed: Invalid auth input"}), 400
        if not validate_input(char, 100):
            return jsonify({"message": "Failed: Invalid character input"}), 400
        if not validate_input(text):
            return jsonify({"message": "Failed: Invalid text input"}), 400

        if len(auth) > 100 or auth != auth_key:
            return jsonify({"message": "Failed: Unauthorized"}), 401

        max_length = int(os.getenv('MAX_INPUT_LENGTH', '10000'))
        if len(text) > max_length:
            return jsonify({"message": "Failed: Input exceeds maximum length"}), 400

        # Use condensed CONTEXT and INTERESTS for relevance analysis (token efficient)
        system_prompt = get_character_context_interests(char)

        # Get OpenAI response
        response = client.chat.completions.create(
            model=model,
            max_tokens=2000,
            temperature=1,
            top_p=1,
            frequency_penalty=1,
            presence_penalty=1,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
        )

        # Return response to caller
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

# Add a message to the character's buffer
def add_message(role, content, character):
    global character_buffers

    # Skip memory for "today" - it's a one-time command, not conversational
    if character == "today":
        return

    # Initialize character buffer if it doesn't exist
    if character not in character_buffers:
        character_buffers[character] = []

    # Add message to character's specific buffer
    character_buffers[character].append({
        "role": role,
        "content": content,
        "timestamp": time.time()
    })

    # Keep only the last 50 messages for THIS character
    character_buffers[character] = character_buffers[character][-50:]

    # Purge messages older than 1 hour for THIS character
    current_time = time.time()
    character_buffers[character] = [
        msg for msg in character_buffers[character]
        if current_time - msg["timestamp"] < 3600
    ]

# Get messages for the current character
def get_char_messages(character):
    # "today" doesn't use memory - it's a one-time command
    if character == "today":
        return []

    if character not in character_buffers:
        return []

    return [
        {"role": msg["role"], "content": msg["content"]}
        for msg in character_buffers[character]
    ]

# Prompts are now handled by prompts.py


# Load configuration from environment
if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', '5000'))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    print(f"Starting MUSH GPT API server on {host}:{port}")
    print(f"Debug mode: {debug}")
    print(f"Model: {model}")
    print(f"Valid characters: {', '.join(prompts)}")

    app.run(host=host, port=port, debug=debug)
