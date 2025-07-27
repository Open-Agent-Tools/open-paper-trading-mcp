import axios from 'axios';
import type { HealthStatus, SystemHealth } from '../types';

// Create separate axios instances for different services
const fastApiClient = axios.create({
  baseURL: 'http://localhost:2080',
  timeout: 5000,
});

const mcpClient = axios.create({
  baseURL: 'http://localhost:2080',
  timeout: 5000,
});

/**
 * Check FastAPI server health
 */
export const checkFastApiHealth = async (): Promise<HealthStatus> => {
  try {
    console.log('Checking FastAPI health at /health');
    const response = await fastApiClient.get('/health');
    console.log('FastAPI health response:', response.status, response.data);
    return {
      service: 'FastAPI',
      status: response.status === 200 && response.data?.status === 'healthy' ? 'healthy' : 'unhealthy',
      statusCode: response.status,
      response: response.data,
      timestamp: Date.now(),
    };
  } catch (error: any) {
    console.error('FastAPI health check failed:', error);
    return {
      service: 'FastAPI',
      status: 'error',
      error: error.message || 'Unknown error',
      timestamp: Date.now(),
    };
  }
};

/**
 * Check MCP server health using the /mcp/health endpoint
 */
export const checkMcpHealth = async (): Promise<HealthStatus> => {
  try {
    console.log('Checking MCP health at /mcp/health');
    const response = await mcpClient.get('/mcp/health');
    console.log('MCP health response:', response.status, response.data);
    return {
      service: 'MCP',
      status: response.status === 200 && response.data?.status === 'healthy' ? 'healthy' : 'unhealthy',
      statusCode: response.status,
      response: response.data,
      timestamp: Date.now(),
    };
  } catch (error: any) {
    console.error('MCP health check failed:', error);
    // MCP server is temporarily disabled due to dependency issues
    if (error.code === 'ECONNREFUSED' || error.message?.includes('Network Error')) {
      return {
        service: 'MCP',
        status: 'unhealthy',
        error: 'MCP server temporarily unavailable (dependency issues)',
        timestamp: Date.now(),
      };
    }
    return {
      service: 'MCP',
      status: 'error',
      error: error.message || 'Unknown error',
      timestamp: Date.now(),
    };
  }
};

/**
 * Check database health via FastAPI's liveness endpoint (simpler check)
 */
export const checkDatabaseHealth = async (): Promise<HealthStatus> => {
  try {
    console.log('Checking database health via /api/v1/trading/accounts');
    const response = await fastApiClient.get('/api/v1/trading/accounts');
    console.log('Database health response:', response.status, response.data);
    return {
      service: 'Database',
      status: response.status === 200 && response.data?.success === true ? 'healthy' : 'unhealthy',
      statusCode: response.status,
      response: response.data,
      timestamp: Date.now(),
    };
  } catch (error: any) {
    console.error('Database health check failed:', error);
    return {
      service: 'Database',
      status: 'error',
      statusCode: error.response?.status,
      error: error.message || 'Unknown error',
      timestamp: Date.now(),
    };
  }
};

/**
 * Check MCP server detailed status
 */
export const checkMcpStatus = async (): Promise<HealthStatus> => {
  try {
    const response = await mcpClient.get('/mcp/status');
    const isHealthy = response.status === 200 && 
                     response.data?.status === 'operational' &&
                     (response.data?.tools_count || 0) > 0;
    
    return {
      service: 'MCP Status',
      status: isHealthy ? 'healthy' : 'unhealthy',
      statusCode: response.status,
      response: response.data,
      timestamp: Date.now(),
    };
  } catch (error: any) {
    return {
      service: 'MCP Status',
      status: 'error',
      error: error.message || 'Unknown error',
      timestamp: Date.now(),
    };
  }
};

/**
 * Check MCP server readiness
 */
export const checkMcpReadiness = async (): Promise<HealthStatus> => {
  try {
    const response = await mcpClient.get('/mcp/ready');
    const isReady = response.status === 200 && response.data?.ready === true;
    
    return {
      service: 'MCP Readiness',
      status: isReady ? 'healthy' : 'unhealthy',
      statusCode: response.status,
      response: response.data,
      timestamp: Date.now(),
    };
  } catch (error: any) {
    return {
      service: 'MCP Readiness',
      status: 'error',
      error: error.message || 'Unknown error',
      timestamp: Date.now(),
    };
  }
};

/**
 * Determine overall system health based on individual service statuses
 */
const determineOverallHealth = (
  fastapi: HealthStatus,
  mcp: HealthStatus,
  database: HealthStatus
): 'healthy' | 'degraded' | 'down' => {
  const services = [fastapi, mcp, database];
  const healthyCount = services.filter(s => s.status === 'healthy').length;
  const errorCount = services.filter(s => s.status === 'error').length;

  if (healthyCount === 3) return 'healthy';
  if (errorCount >= 2) return 'down';
  return 'degraded';
};

/**
 * Check all system health endpoints
 */
export const checkSystemHealth = async (): Promise<SystemHealth> => {
  try {
    const [fastApiHealth, mcpHealth, databaseHealth] = await Promise.allSettled([
      checkFastApiHealth(),
      checkMcpHealth(),
      checkDatabaseHealth(),
    ]);

    const fastapi: HealthStatus = fastApiHealth.status === 'fulfilled' 
      ? fastApiHealth.value 
      : { service: 'FastAPI', status: 'error', error: 'Check failed', timestamp: Date.now() };

    const mcp: HealthStatus = mcpHealth.status === 'fulfilled' 
      ? mcpHealth.value 
      : { service: 'MCP', status: 'error', error: 'Check failed', timestamp: Date.now() };

    const database: HealthStatus = databaseHealth.status === 'fulfilled' 
      ? databaseHealth.value 
      : { service: 'Database', status: 'error', error: 'Check failed', timestamp: Date.now() };

    const overall = determineOverallHealth(fastapi, mcp, database);

    return {
      fastapi,
      mcp,
      database,
      overall,
    };
  } catch (error) {
    // Fallback if Promise.allSettled somehow fails
    return {
      fastapi: { service: 'FastAPI', status: 'unknown', error: 'System check failed', timestamp: Date.now() },
      mcp: { service: 'MCP', status: 'unknown', error: 'System check failed', timestamp: Date.now() },
      database: { service: 'Database', status: 'unknown', error: 'System check failed', timestamp: Date.now() },
      overall: 'down',
    };
  }
};

export default {
  checkFastApiHealth,
  checkMcpHealth,
  checkDatabaseHealth,
  checkMcpStatus,
  checkMcpReadiness,
  checkSystemHealth,
};