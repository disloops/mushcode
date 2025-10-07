# MUSH GPT API Server

A centralized API server for MUSH (Multi-User Shared Hallucination) bots that provides AI-powered character interactions.

## Features

- **Multiple Character Support**: Oracle, Daemon, Ptolemy, Today Bot, and Starlink
- **Token Optimization**: Uses condensed prompts for efficiency
- **Security**: Input validation and sanitization
- **Memory Management**: Character-specific conversation buffers
- **Rate Limiting**: Prevents abuse and spam
- **Logging**: Comprehensive logging with rotation

## Setup

1. **Install Dependencies**:
   ```bash
   pip install flask openai requests
   ```

2. **Configure Environment**:
   ```bash
   cp mush_gpt.env.example mush_gpt.env
   # Edit mush_gpt.env with your settings
   ```

3. **Deploy as Service**:
   ```bash
   ./start.sh deploy
   ```

## API Endpoints

- `/bot` - Main character interaction endpoint
- `/cmd` - Command-based interactions (like +today)
- `/adhoc` - Token-efficient endpoint for special requests

## Configuration

See `mush_gpt.env.example` for all configuration options.

## Security

- Input validation and sanitization
- Authentication via API keys
- Rate limiting (cooldowns removed to allow natural conversations)
- Unicode normalization for MUSH compatibility
