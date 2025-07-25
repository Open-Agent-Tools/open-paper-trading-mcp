export interface AccountInfo {
  owner: string;
  cash_balance: number;
}

export interface Position {
  id: string;
  symbol: string;
  quantity: number;
  average_price: number;
  value: number;
}

export interface NewOrder {
  symbol: string;
  quantity: number;
  type: 'MARKET' | 'LIMIT';
  price?: number;
}

export interface Order extends NewOrder {
    id: string;
    status: 'PENDING' | 'FILLED' | 'CANCELLED';
}

export interface HealthStatus {
  service: string;
  status: 'healthy' | 'unhealthy' | 'error' | 'unknown';
  statusCode?: number;
  response?: any;
  error?: string;
  timestamp?: number;
}

export interface SystemHealth {
  fastapi: HealthStatus;
  mcp: HealthStatus;
  database: HealthStatus;
  overall: 'healthy' | 'degraded' | 'down';
}
