# Docker Setup for Open Paper Trading MCP

## Overview

This document describes the Docker containerization setup for the Open Paper Trading MCP application.

## Services

The application runs as a multi-service Docker setup with the following components:

### 1. Database Service (`db`)
- **Image**: `postgres:15-alpine`
- **Port**: `5432`
- **Credentials**: 
  - User: `trading_user`
  - Password: `trading_password`
  - Database: `trading_db`
- **Health Check**: Built-in PostgreSQL readiness check

### 2. Application Service (`app`)
- **Build**: Uses custom Dockerfile
- **Ports**: 
  - `2080`: FastAPI server (REST API + React frontend)
  - `2081`: MCP server (AI agent tools)
- **Environment Variables**:
  - Database configuration automatically connects to `db` service
  - Test data adapter enabled by default
  - Robinhood credentials can be overridden via environment variables

## Quick Start

To start all services:

```bash
docker-compose up -d
```

## Service Endpoints

Once running, the following endpoints are available:

- **FastAPI Server**: http://localhost:2080
  - Health check: http://localhost:2080/health
  - API documentation: http://localhost:2080/docs
  - React frontend: http://localhost:2080/ (if built)

- **MCP Server**: http://localhost:2081
  - Provides 43 MCP tools for AI agent interaction
  - Tools organized in 7 functional sets

- **Database**: localhost:5432 (PostgreSQL)

## Architecture Features

### Split Server Design
- FastAPI server handles REST API and frontend serving
- MCP server runs independently for AI agent tools
- Both servers share the same TradingService business logic
- Database migrations handled automatically on startup

### Development Features
- Source code mounted as volume for development (read-only)
- Persistent token storage for Robinhood authentication
- Comprehensive logging and health checks
- Automatic database migration on startup

## Configuration

Key configuration options:

### Environment Variables
- `ROBINHOOD_USERNAME`: Your Robinhood username
- `ROBINHOOD_PASSWORD`: Your Robinhood password  
- `QUOTE_ADAPTER_TYPE`: Set to "robinhood" for live data, "test" for mock data
- `DATABASE_URL`: Automatically configured for Docker network

### Docker Compose Override
To use live Robinhood data, create a `.env` file:

```bash
ROBINHOOD_USERNAME=your_username
ROBINHOOD_PASSWORD=your_password
QUOTE_ADAPTER_TYPE=robinhood
```

## Status

✅ **Production Ready**: Both FastAPI and MCP servers running successfully
✅ **Database Integration**: PostgreSQL connected and migrations working
✅ **Health Checks**: All services have proper health monitoring
✅ **Network Isolation**: Services communicate via Docker network
✅ **Persistent Storage**: Database and token data preserved across restarts

## Development Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Restart application only
docker-compose restart app

# Stop all services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

## Next Steps

1. **Frontend Build**: Run `cd frontend && npm run build` to enable React frontend
2. **Live Data**: Configure Robinhood credentials for real market data
3. **Production**: Update secrets and security settings for production deployment