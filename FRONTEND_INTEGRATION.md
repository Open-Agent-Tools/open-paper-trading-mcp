# FastAPI + MCP + React Integration

This project integrates React frontend, MCP server, and FastAPI into a unified single-server architecture following the TestDriven.io approach with FastMCP.

## Architecture

```
FastAPI Server (Port 2080)
├── / → React App (SPA)
├── /api/* → REST API endpoints  
├── /mcp/* → MCP (Model Context Protocol) server
├── /health → Health check
├── /docs → API documentation
└── /static/* → React build assets
```

## Development Workflow

### Option 1: Build and Serve (Recommended)
```bash
# Build React app and start FastAPI server
python scripts/serve_frontend.py
```

### Option 2: Manual Steps
```bash
# 1. Build React frontend
cd frontend
npm run build

# 2. Start FastAPI server (from project root)
cd ..
python app/main.py
```

### Option 3: Frontend Development
```bash
# For React development with hot reload
cd frontend
npm run dev  # Serves on port 5173 with API proxy
```

## Key Features

✅ **Single Port**: Everything served from port 2080  
✅ **SPA Routing**: React Router works with FastAPI catch-all  
✅ **API Integration**: React app uses relative URLs (`/api/v1/`)  
✅ **MCP Integration**: Model Context Protocol server at `/mcp/`  
✅ **Health Check**: MCP tool for system health monitoring  
✅ **Static Assets**: Proper serving of JS/CSS bundles  
✅ **Development Proxy**: Vite dev server proxies API calls  

## File Structure

```
app/
├── main.py                 # FastAPI server with React + MCP integration
├── mcp_tools.py           # MCP tools (health check)
frontend/
├── dist/                   # Built React app (served by FastAPI)
├── src/                    # React source code
├── vite.config.ts         # Vite config with proxy setup
└── package.json           # npm scripts
scripts/serve_frontend.py   # Development helper script
```

## Configuration Details

### Vite Configuration (`frontend/vite.config.ts`)
- **Build Output**: `dist/` with assets in `static/` subdirectory
- **Dev Proxy**: API calls proxied to `http://localhost:2080`
- **Relative URLs**: React app uses relative API paths

### FastAPI Configuration (`app/main.py`)
- **Static Files**: Mounted at `/static` for React assets
- **MCP Server**: Mounted at `/mcp` using FastMCP
- **SPA Routing**: Catch-all route serves React app for client-side routes
- **Route Protection**: API and MCP routes excluded from catch-all handler

### React API Client (`frontend/src/services/apiClient.ts`)
- **Base URL**: `/api/v1` (relative to current domain)
- **Development**: Works with Vite proxy to FastAPI
- **Production**: Direct calls to same-origin FastAPI server

## Testing

Run the integration test:
```bash
python test_integration.py
```

This verifies:
- ✅ Health endpoint responds correctly
- ✅ MCP server responds at `/mcp/`
- ✅ React app serves from root `/`
- ✅ Client-side routing works (e.g., `/dashboard`)

## Benefits

1. **Simplified Deployment**: Single Docker container, one port
2. **Unified Logging**: All requests go through FastAPI middleware  
3. **Shared Resources**: Database connections, auth, etc.
4. **Production Ready**: Follows FastAPI + React best practices
5. **Development Friendly**: Hot reload for React, API integration works seamlessly