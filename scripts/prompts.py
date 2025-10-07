#!/usr/bin/env python

# MIT License
# Copyright (c) 2024 Matt Westfall (@disloops)

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

"""
Character prompts for MUSH GPT API server.
Each character has its own prompt that defines its personality and behavior.
Handles all prompt-specific logic including astronomical context.
"""

import time
import subprocess
import sys
import os
import re
from datetime import datetime

# Load prompts from text file
def load_prompts_file(filepath):
    """Load prompts from a robust text file format"""
    prompts = {}
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split by section headers (must be at start of line)
        sections = re.split(r'^\[([A-Z_]+)\]$', content, flags=re.MULTILINE)

        # Process sections (odd indices are section names, even indices are content)
        for i in range(1, len(sections), 2):
            if i + 1 < len(sections):
                section_name = sections[i].lower()
                section_content = sections[i + 1].strip()

                # Only add non-empty sections
                if section_content:
                    prompts[section_name] = section_content

    return prompts

# Load prompts from text file
prompts_data = load_prompts_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompts.txt'))

# Validate loaded prompts
def validate_prompts(prompts_data):
    """Validate that all required prompts are loaded"""
    required_prompts = ['oracle', 'daemon', 'ptolemy', 'today', 'starlink']
    missing_prompts = []

    for prompt in required_prompts:
        if prompt not in prompts_data or not prompts_data[prompt].strip():
            missing_prompts.append(prompt)

    if missing_prompts:
        print(f"Warning: Missing or empty prompts: {', '.join(missing_prompts)}")
        print("Using default prompts for missing characters.")

    return len(missing_prompts) == 0

# Validate prompts on load
validate_prompts(prompts_data)

def substitute_placeholders(text):
    """Substitute placeholders in prompt text with current values"""
    if not text:
        return text

    # Get current date/time
    now = datetime.now()

    # Replace {today} with current date
    text = text.replace('{today}', now.strftime('%B %d, %Y'))

    # Replace {time} with current time
    text = text.replace('{time}', now.strftime('%H:%M:%S'))

    # Replace {datetime} with current date and time
    text = text.replace('{datetime}', now.strftime('%B %d, %Y at %H:%M:%S'))

    return text

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

def get_oracle_prompt():
    """Oracle character prompt"""
    base_prompt = prompts_data.get('oracle', 'You are the Oracle, an ancient seer with mystical powers.')
    return substitute_placeholders(base_prompt)

def get_daemon_prompt():
    """Daemon character prompt"""
    base_prompt = prompts_data.get('daemon', 'You are a daemon, a helpful assistant.')
    return substitute_placeholders(base_prompt)

def get_ptolemy_prompt():
    """Ptolemy character prompt with astronomical context"""
    base_prompt = prompts_data.get('ptolemy', 'You are Ptolemy, the ancient astronomer and astrologer.')
    base_prompt = substitute_placeholders(base_prompt)
    astro_context = get_astronomical_context()
    return f"{base_prompt}{astro_context}"

def get_today_prompt():
    """Today bot prompt with astronomical context"""
    base_prompt = prompts_data.get('today', 'You are the Today Bot, a helpful assistant that provides daily information.')
    base_prompt = substitute_placeholders(base_prompt)
    astro_context = get_astronomical_context()
    return f"{base_prompt}{astro_context}"

def get_starlink_prompt():
    """Starlink bot prompt"""
    base_prompt = prompts_data.get('starlink', 'You are Starlink, a futuristic AI assistant with advanced communication capabilities.')
    return substitute_placeholders(base_prompt)

def get_character_context_interests(character):
    """Extract CONTEXT and INTERESTS sections from any character prompt for relevance analysis"""
    full_prompt = prompts_data.get(character, '')

    # Parse sections using the same robust method as load_prompts_file
    sections = {}
    if full_prompt:
        # Split by section headers (must be at start of line)
        section_parts = re.split(r'^([A-Z_]+):\s*$', full_prompt, flags=re.MULTILINE)

        # Process sections (odd indices are section names, even indices are content)
        for i in range(1, len(section_parts), 2):
            if i + 1 < len(section_parts):
                section_name = section_parts[i].upper()
                section_content = section_parts[i + 1].strip()

                # Stop at the next section header by finding the first line that looks like a header
                lines = section_content.split('\n')
                content_lines = []
                for line in lines:
                    # If we hit a line that looks like a section header, stop
                    if re.match(r'^[A-Z_]+:\s*$', line.strip()):
                        break
                    content_lines.append(line)

                # Join the content and clean it up
                clean_content = '\n'.join(content_lines).strip()
                if clean_content:
                    sections[section_name] = clean_content

    # Extract CONTEXT and INTERESTS sections
    context = sections.get('CONTEXT', '').strip()
    interests = sections.get('INTERESTS', '').strip()

    # Combine and substitute placeholders
    combined = f"CONTEXT: {context}\n\nINTERESTS: {interests}"
    return substitute_placeholders(combined)

def get_starlink_context_interests():
    """Extract just CONTEXT and INTERESTS sections from Starlink prompt for relevance analysis"""
    return get_character_context_interests('starlink')

def get_valid_prompts():
    """
    Get a list of all valid prompt characters.

    Returns:
        list: List of valid character names
    """
    return ["oracle", "daemon", "ptolemy", "today", "starlink"]

def get_prompt(character):
    """
    Get the prompt for a specific character.
    All prompt-specific logic (including astronomical context) is handled internally.

    Args:
        character (str): The character name

    Returns:
        str: The character's prompt
    """
    if character == "oracle":
        return get_oracle_prompt()
    elif character == "daemon":
        return get_daemon_prompt()
    elif character == "ptolemy":
        return get_ptolemy_prompt()
    elif character == "today":
        return get_today_prompt()
    elif character == "starlink":
        return get_starlink_prompt()
    else:
        return f"Unknown character: {character}"

if __name__ == "__main__":
    # Test the prompts
    print("=== VALID PROMPTS ===")
    print(get_valid_prompts())
    print("\n=== ORACLE ===")
    print(get_prompt("oracle"))
    print("\n=== DAEMON ===")
    print(get_prompt("daemon"))
    print("\n=== PTOLEMY ===")
    print(get_prompt("ptolemy"))
    print("\n=== TODAY ===")
    print(get_prompt("today"))
    print("\n=== STARLINK ===")
    print(get_prompt("starlink"))
