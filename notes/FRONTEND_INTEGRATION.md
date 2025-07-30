# FastAPI + MCP + React Integration

This project integrates React frontend, MCP server, and FastAPI using a **split architecture** approach that resolves FastMCP mounting conflicts while maintaining unified functionality.

## Current Architecture (Split Servers)

```
Port 2080: FastAPI Server        Port 2081: MCP Server
├── / → React App (SPA)          ├── /mcp → MCP Protocol Endpoint
├── /api/* → REST API endpoints  ├── Tools: health_check
├── /health → Health check       ├── Tools: get_account_balance
├── /docs → API documentation    ├── Tools: get_account_info
└── /static/* → React assets     ├── Tools: get_portfolio
                                 ├── Tools: get_portfolio_summary
                                 └── Tools: list_tools
```

## Architecture Evolution

### Previous: Single Server (Mounting Conflicts)
- FastMCP mounted at `/mcp/*` on port 2080
- **Issue**: FastMCP mounting conflicts with FastAPI routing
- **Result**: MCP tools inaccessible, 404 errors

### Current: Split Architecture (Resolved)
- **FastAPI Server (2080)**: Frontend + REST API endpoints
- **MCP Server (2081)**: Independent FastMCP server with tools
- **Benefit**: Both interfaces operational, no mounting conflicts

## Development Workflow

### Option 1: Full Stack (Docker - Recommended)
```bash
# Start both servers + database + frontend
docker-compose up --build
# Access: Frontend (2080), MCP Server (2081), API Docs (2080/docs)
```

### Option 2: Split Development
```bash
# Terminal 1: Start FastAPI server (frontend + REST API)
uv run python app/main.py  # Port 2080

# Terminal 2: Start MCP server (AI agent tools)  
uv run python app/mcp_server.py  # Port 2081

# Terminal 3: Frontend development with hot reload
cd frontend && npm run dev  # Port 5173 with API proxy
```

### Option 3: Individual Components
```bash
# FastAPI server only
python scripts/dev.py server

# Build React frontend manually
cd frontend && npm run build

# Test MCP server independently
curl http://localhost:2081/mcp -H "Content-Type: application/json"
```

## Key Features

✅ **Split Architecture**: FastAPI (2080) + MCP (2081) servers running independently  
✅ **Dual Interface Access**: Web clients via REST API, AI agents via MCP tools  
✅ **SPA Routing**: React Router works with FastAPI catch-all  
✅ **API Integration**: React app uses relative URLs (`/api/v1/`)  
✅ **MCP Protocol**: Independent MCP server with 6 tools + list_tools function  
✅ **Health Monitoring**: Both REST API and MCP tool health checks  
✅ **Static Assets**: Proper serving of JS/CSS bundles from FastAPI  
✅ **Development Proxy**: Vite dev server proxies API calls  
✅ **Service Unity**: Both interfaces use identical TradingService via dependency injection  
✅ **Auto Documentation**: FastAPI generates API docs at `/docs`  

## File Structure

```
app/
├── main.py                 # FastAPI server (frontend + REST API)
├── mcp_server.py           # Independent MCP server
├── mcp_tools.py            # MCP tools (6 tools + list_tools)
├── api/v1/trading.py       # REST API endpoints mirroring MCP tools
├── core/service_factory.py # Dependency injection for TradingService
frontend/
├── dist/                   # Built React app (served by FastAPI)
├── src/                    # React source code with API client
├── vite.config.ts          # Vite config with proxy to port 2080
└── package.json            # npm scripts and dependencies
scripts/
├── serve_frontend.py       # Development helper script
└── dev.py                  # Development command runner
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