# Starlink MUSH Bot

An MUSH bot that listens on <Public> and responds based on commands and relevance.

## Features

- **Dual Response Modes**:
  - Subscriber-style requests based on membership, location, etc.
  - AI-driven relevance analysis for general chat messages
- **Master Player Check**: Only responds when a specific player is online
- **Token Optimization**: Uses efficient prompts for relevance analysis
- **Security**: Comprehensive input validation and sanitization

## Setup

1. **Install Dependencies**:
   ```bash
   pip install requests psutil
   ```

2. **Configure Environment**:
   ```bash
   cp starlink.env.example starlink.env
   # Edit starlink.env with your settings
   ```

3. **Deploy as Service**:
   ```bash
   ./start.sh deploy
   ```

## Configuration

- `TARGET_LOCATIONS`: Comma-separated list of DBRefs where asterisk-prefaced requests work
- `MASTER_PLAYER_DBREF`: DBREF of player who must be online for responses to occur
- `API_URL`: URL of the MUSH GPT API server
- `RATE_LIMIT_WINDOW`: Time window for rate limiting
