# Health Monitoring Components

This directory contains components for monitoring the health status of the Open Paper Trading system services.

## Components

### SystemHealthIndicator
The main component that displays system health status in various formats.

**Props:**
- `compact?: boolean` - Display in compact horizontal layout
- `showDetails?: boolean` - Show additional details and tooltips
- `variant?: 'full' | 'summary' | 'minimal'` - Display variant
- `refreshInterval?: number` - Auto-refresh interval in milliseconds

**Variants:**
- `minimal` - Just a status dot and overall text
- `summary` - API status, market status, with optional details tooltip (default for footer)
- `full` - Complete service breakdown with individual status indicators

### StatusIndicator
Individual service status display component.

**Props:**
- `healthStatus: HealthStatus` - Health status object for the service
- `showService?: boolean` - Whether to show service name
- `size?: 'small' | 'medium'` - Size of status indicators
- `variant?: 'chip' | 'dot' | 'text' | 'full'` - Display style

### HealthDashboard
Comprehensive health monitoring dashboard for admin/debug views.

**Props:**
- `autoRefresh?: boolean` - Enable automatic refresh
- `refreshInterval?: number` - Auto-refresh interval in milliseconds

## Services

### healthService.ts
Core service that checks health of all system components:
- **FastAPI** (port 2080) - Main REST API server
- **MCP** (port 2081) - Model Context Protocol server
- **Database** - Via FastAPI database-dependent endpoints

### useHealthMonitor.ts
React hook for health monitoring with automatic polling and state management.

## Color Scheme

Colors are aligned with the project style guide (`PRD_files/style_guide.html`):

- **Healthy (Success)**: `#006b3c` - Green for operational services
- **Degraded (Warning)**: `#b45309` - Orange for services with issues
- **Offline (Error)**: `#dc3545` - Red for failed services
- **Unknown**: `#6c757d` - Gray for unknown status

## Usage Examples

### Footer Status (Current Implementation)
```tsx
<SystemHealthIndicator 
  variant="summary" 
  showDetails={true}
  refreshInterval={30000}
/>
```

### Dashboard Health Panel
```tsx
<HealthDashboard 
  autoRefresh={true}
  refreshInterval={15000}
/>
```

### Individual Service Status
```tsx
<StatusIndicator 
  healthStatus={healthStatus}
  variant="dot"
  showService={true}
/>
```

## Integration Notes

- The health monitoring runs independently of the main API calls
- Failed health checks do not prevent the app from functioning
- Health status is cached and refreshed on intervals to avoid overwhelming servers
- All health checks have 5-second timeouts to prevent hanging
- Polling automatically handles server unavailability gracefully

## Development

When servers are not running, the health indicators will show "Offline" status but won't crash the application. This allows for development even when services are down.