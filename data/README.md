# Data Directory

This directory contains persistent data for the Open Paper Trading MCP application.

## Structure

```
data/
├── tokens/     # Robinhood authentication tokens (persistent across container restarts)
├── logs/       # Application logs (persistent across container restarts)
└── README.md   # This file
```

## Token Storage

The `tokens/` directory is used to store Robinhood authentication tokens to avoid having to re-authenticate on every container restart. This follows the same pattern as the reference open-stocks-mcp implementation.

### Token Files

- `robinhood.pickle` - Pickled Robinhood session data
- Other token files as needed by the authentication system

## Log Storage

The `logs/` directory stores application logs that persist across container restarts.

## Docker Volume Configuration

These directories are mounted as bind volumes in the Docker Compose configuration:

```yaml
volumes:
  robinhood_tokens:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ./data/tokens
  trading_logs:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ./data/logs
```

## Security Notes

- The `tokens/` directory should be excluded from version control
- Ensure proper file permissions are set on token files
- Consider encrypting sensitive token data in production environments

## Environment Variables

The application uses the following environment variable to locate the token storage:

- `ROBINHOOD_TOKEN_PATH=/app/.tokens` - Path to token storage directory inside the container