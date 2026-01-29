# Starlink MUSH Bot

A MUSH bot that listens on <Public> and responds based on commands and relevance.

## Features

- **Dual Response Modes**:
  - Subscriber-style requests based on membership, location, etc.
  - AI-driven relevance analysis for general chat messages
- **Master Player Check**: Only responds when a specific player is online
- **Token Optimization**: Uses efficient prompts for relevance analysis
- **Security**: Comprehensive input validation and sanitization
- **Self-Contained Prompt**: Bot's personality is defined in its own `starlink.prompt` file

## Setup

1. **Install Dependencies**:
   ```bash
   pip install requests
   ```

2. **Configure Environment**:
   ```bash
   cp starlink.env.example starlink.env
   # Edit starlink.env with your settings
   ```

3. **Configure Prompt** (REQUIRED):
   ```bash
   cp starlink.prompt.example starlink.prompt
   # Edit starlink.prompt with your bot's personality
   ```

4. **Deploy as Service**:
   ```bash
   ./start.sh deploy
   ```

## Configuration

All settings are required (no hardcoded defaults). See `starlink.env.example` for a complete template.

### Required Settings
- `MUSH_HOST`, `MUSH_PORT`, `BOT_NAME`, `BOT_PASSWORD`: MUSH connection
- `MUSH_TIMEOUT`: Socket timeout for MUSH connection
- `API_AUTH_KEY`, `API_URL`, `API_TIMEOUT`: API connection
- `LLM_PROVIDER`: Must be 'openai' or 'gemini'
- `CHARACTER_NAME`: Identifier for conversation buffer management
- `MESSAGE_DELAY`, `MAX_RETRIES`, `RETRY_DELAY`: Bot behavior
- `RATE_LIMIT_WINDOW`, `MAX_RESPONSES_PER_WINDOW`: Rate limiting
- `LOG_LEVEL`, `LOG_FILE`: Logging configuration
- `RESTRICT_USAGE`: Set to TRUE or FALSE

### Required File
- `starlink.prompt`: The bot's system prompt (see `starlink.prompt.example`)

### Conditional Settings (required when RESTRICT_USAGE=TRUE)
- `TARGET_LOCATIONS`: Comma-separated list of DBRefs where asterisk-prefaced requests work
- `LOG_BOOK_DBREF`: DBREF for membership checking

### Optional Settings (even when RESTRICT_USAGE=TRUE)
- `MASTER_PLAYER_DBREF`: DBREF of player who must be online for responses
- `RESTRICTION_MESSAGE`: Custom message when user is restricted (use `{locations}` for location list)

## Prompt File Format

The `starlink.prompt` file should contain these sections:

```
CONTEXT:
Describe your bot's setting and role...

PERSONALITY:
Describe personality traits, beliefs, attitudes...

INTERESTS:
List topics your bot engages with...

FUNCTIONALITY:
Standard bot behavior instructions...

SECURITY CONSTRAINTS:
Safety and security rules...
```

See `starlink.prompt.example` for a complete template.
