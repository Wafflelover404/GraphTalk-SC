# UI Tools & Alternative Interfaces

This directory contains alternative user interface implementations and bot integrations that provide different ways to interact with the GraphTalk system.

## Available Tools

### `sc_machine_ui.py`
Semantic Code Machine User Interface

**Purpose:** Provides a UI for interacting with the semantic code knowledge base

**Features:**
- Interactive interface for SC (Semantic Code) queries
- Document browsing and search
- Knowledge base visualization
- Alternative to the main web API

**Usage:**
```bash
python sc_machine_ui.py
```

**When to use:**
- Local development and testing
- Advanced semantic code interactions
- Data exploration and debugging

### `tg_bot.py`
Telegram Bot Integration

**Purpose:** Provides Telegram bot interface to the RAG system

**Features:**
- Query the knowledge base via Telegram
- Support for multiple users
- Command-based interface
- Real-time response delivery

**Usage:**
```bash
# Set up environment variables first
export TELEGRAM_BOT_TOKEN="your_token_here"

# Run the bot
python tg_bot.py
```

**When to use:**
- Providing knowledge base access via Telegram
- Mobile-friendly interface
- Integration with Telegram workflows
- Chat-based interactions

## Configuration

### Telegram Bot Setup

1. Create a bot with BotFather on Telegram
2. Set the bot token in environment variables
3. Configure webhook or polling settings
4. Run the bot script

### UI Tool Setup

1. Ensure all dependencies are installed
2. Configure database connections
3. Set up authentication if needed
4. Run the tool

## Relationship to Main API

These tools are **alternatives to** and **in addition to** the main REST API (`api.py`):

- **Main API (api.py):** Web-based REST endpoints for web frontend
- **SC API (api_sc.py):** Semantic Code specific endpoints
- **UI Tools:** Alternative interfaces for specialized use cases

## Development & Testing

These tools are useful for:
- Developing new features
- Testing functionality
- Providing specialized interfaces
- Integrating with external platforms

## Performance Considerations

- Both tools share the same backend resources
- They may impact performance if used simultaneously with the main API
- Consider resource allocation for production use
- Monitor system load when running multiple interfaces

## Deployment Notes

- These tools are optional for production
- Deploy only if you need the specific functionality
- Can run on separate servers/containers
- Ensure proper authentication and security

## Troubleshooting

If tools aren't working:
1. Verify dependencies are installed
2. Check environment variable configuration
3. Ensure database connections are available
4. Review application logs for errors
5. Test with simple queries first

## Future Development

These tools can be extended to:
- Support additional platforms (Discord, Slack, etc.)
- Add new interface paradigms
- Implement specialized features
- Improve user experience

For more information on the main API, see the parent directory documentation.
