# MUSH GPT API Server

A centralized API server for MUSH (Multi-User Shared Hallucination) bots that provides AI-powered character interactions.

## Features

- **Multiple Character Support**: Oracle, Daemon, Ptolemy, Today Bot, and more
- **Switchable LLM Providers**: OpenAI (Responses API) or Google Gemini (via `LLM_PROVIDER` env var)
- **Token Optimization**: Uses condensed prompts for efficiency
- **Security**: Input validation and sanitization
- **Memory Management**: Character-specific conversation buffers
- **Rate Limiting**: Prevents abuse and spam
- **Logging**: Comprehensive logging with rotation
- **Direct Prompt Support**: Bots can pass their own system prompts directly

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
