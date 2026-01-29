# MUSH GPT API Server

A centralized API server for MUSH (Multi-User Shared Hallucination) bots that provides AI-powered character interactions.

## Features

- **Dynamic Character Support**: Define any characters in `prompts.txt` - no code changes needed
- **Switchable LLM Providers**: OpenAI (Responses API) or Google Gemini (via `LLM_PROVIDER` env var)
- **Token Optimization**: Uses condensed prompts for efficiency
- **Security**: Input validation, character name sanitization, and output cleaning
- **Memory Management**: Character-specific conversation buffers (configurable per-character)
- **Rate Limiting**: Prevents abuse and spam
- **Logging**: Comprehensive logging with rotation
- **Direct Prompt Support**: Bots can pass their own system prompts directly
- **Astronomical Data**: Optional integration for characters needing celestial context

## Setup

1. **Install Dependencies**:
   ```bash
   pip install flask
   pip install openai        # if using OpenAI
   pip install google-genai  # if using Gemini
   ```

2. **Configure Environment**:
   ```bash
   cp mush_gpt.env.example mush_gpt.env
   # Edit mush_gpt.env - ALL settings are required, no defaults
   ```

3. **Deploy as Service**:
   ```bash
   ./start.sh deploy
   ```

Default production path: `/home/ubuntu/mush_gpt/`

## API Endpoints

### `/bot` - Main character interaction endpoint
Parameters:
- `auth` (required): Authentication key
- `text` (required): User message
- `char` (required): Character identifier for conversation buffer
- `context_only` (optional): If true, only adds to context without response
- `prompt_file` (optional): Custom prompt file path
- `system_prompt` (optional): Direct system prompt (bypasses char lookup)
- `provider` (optional): Override LLM provider ('openai' or 'gemini')

### `/cmd` - Command-based interactions (like +today)

### `/adhoc` - Token-efficient endpoint for special requests
Accepts same parameters as `/bot`, including `system_prompt` for direct prompts.

## Configuration

See `mush_gpt.env.example` for all configuration options.

### Character Configuration

Characters are defined in `prompts.txt` using this format:

```
[CHARACTER_NAME]
Your character prompt here...
Use {today}, {time}, {datetime} for dynamic placeholders.
```

Optional character settings in `mush_gpt.env`:

- `ASTRO_CHARACTERS`: Comma-separated list of characters that need astronomical data appended (e.g., `ptolemy,today`)
- `STATELESS_CHARACTERS`: Comma-separated list of characters that don't maintain conversation history (e.g., `today`)
