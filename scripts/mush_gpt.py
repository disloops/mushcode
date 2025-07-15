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
# ASTRONOMICAL DATA INTEGRATION:
# - Fetches real astronomical data from NASA's JPL Horizons API
# - Provides accurate moon phases, planetary positions, and zodiac signs
# - Automatically embeds astronomical data into "astro" and "today" bot prompts
# - Uses NASA's official ephemeris data for reliability and accuracy
# - No API keys required for NASA data (free and official)

from flask import Flask, request, jsonify
from openai import AsyncOpenAI, OpenAI
import datetime
import time
import os
import sys
import json

app = Flask(__name__)

# OpenAI API key
client = OpenAI(api_key="[API key here]")

# Pseudo-secret password value that must be present in incoming requests
auth_key = "[auth value here]"

# Valid MUSH cases for which a system pre-prompt exists
prompts = ["oracle","daemon","astro","today"]

# Model (may depend on the prompt scenario)
model = "gpt-4.1"

# Add message buffer
message_buffer = []

# Astronomy data cache
astro_cache = {}
astro_cache_time = 0
CACHE_DURATION = 3600  # Cache for 1 hour

def get_astronomical_context():
    """Get current astronomical data for inclusion in prompts (cached for performance)"""
    global astro_cache, astro_cache_time

    current_time = time.time()

    # Return cached data if still valid
    if current_time - astro_cache_time < CACHE_DURATION and astro_cache:
        return astro_cache.get('context', '')

    try:
        # Execute astronomy_data.py with --bot flag for clean output
        import subprocess
        import os

        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'astronomy_data.py')
        result = subprocess.run(
            [sys.executable, script_path, '--bot'],
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )

        if result.returncode == 0 and result.stdout.strip():
            summary = result.stdout.strip()
            context = f"\n\nCurrent Astronomical Data: {summary}"
            # Cache the result
            astro_cache = {'context': context, 'summary': summary}
            astro_cache_time = current_time
            return context
        else:
            return "\n\nCurrent Astronomical Data: Unable to fetch data"
    except subprocess.TimeoutExpired:
        print("Error: Astronomy data fetch timed out")
        return "\n\nCurrent Astronomical Data: Timeout fetching data"
    except Exception as e:
        print(f"Error fetching astronomical data: {e}")
        return "\n\nCurrent Astronomical Data: Error fetching data"

@app.route('/today', methods=['POST'])
def today():
    try:
        # Check for POST parameters
        json_data = request.get_json()
        if not json_data or 'auth' not in json_data:
            return jsonify({"message": "Failed: Invalid request data"}), 400

        auth = json_data['auth'].strip()

        if len(auth) > 100 or auth != auth_key:
            return jsonify({"message": "Failed: Unauthorized"}), 401

        # Format request to OpenAI API endpoint
        response = client.chat.completions.create(
            model=model,
            max_tokens=1000,
            temperature=1,
            top_p=1,
            frequency_penalty=1,
            presence_penalty=1,
            messages=[
                {"role": "system", "content": prompt("today")}
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
            return jsonify({"message": message_content})

    except Exception as e:
        return jsonify({"message": "Failed: Error"}), 500

@app.route('/', methods=['POST'])
def index():
    try:

        # Check for POST parameters
        json_data = request.get_json()
        if not json_data or 'text' not in json_data or 'auth' not in json_data or 'char' not in json_data:
            return jsonify({"message": "Failed: Invalid request data"}), 400

        text = json_data['text'].strip()
        auth = json_data['auth'].strip()
        char = json_data['char'].strip()

        if len(auth) > 100 or auth != auth_key:
            return jsonify({"message": "Failed: Unauthorized"}), 401

        if len(text) > 500:
            return jsonify({"message": "Failed: Input exceeds maximum length"}), 400

        if len(char) > 100 or char not in prompts:
            return jsonify({"message": "Failed: Invalid character reference"}), 400

        # Add user message to the buffer
        add_message("user", text, char)

        # Filter messages for the current character
        char_messages = get_char_messages(char)

        # Format request to OpenAI API endpoint
        response = client.chat.completions.create(
            model=model,
            max_tokens=1000,
            temperature=1,
            top_p=1,
            frequency_penalty=1,
            presence_penalty=1,
            messages=[
                {"role": "system", "content": prompt(char)},
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
            add_message("assistant", message_content, char)
            return jsonify({"message": message_content})

    except Exception as e:
        return jsonify({"message": "Failed: Error"}), 500

# Add a message to the buffer
def add_message(role, content, character):
    global message_buffer

    message_buffer.append({"role": role, "content": content, "timestamp": time.time(), "character": character})

    # Keep only the last 10 messages
    message_buffer = message_buffer[-19:]

    # Purge messages older than 1 hour
    current_time = time.time()
    message_buffer = [msg for msg in message_buffer if current_time - msg["timestamp"] < 3600]

# Get filtered messages for the current character
def get_char_messages(character):
    return [
        {"role": msg["role"], "content": msg["content"]}
        for msg in message_buffer
        if msg.get("character") == character
    ]

# Return an existing character prompt
def prompt(char):
    if char == "oracle":
        return """[Put your oracle prompt here]"""
    elif char == "daemon":
        return """[Put your daemon prompt here]"""
    elif char == "astro":
        astro_context = get_astronomical_context()
        return f"""[Put your astro prompt here]{astro_context}"""
    elif char == "today":
        astro_context = get_astronomical_context()
        return f"""[Put your +today prompt here]{astro_context}"""


# Use default port 5000
if __name__ == '__main__':
    app.run()
