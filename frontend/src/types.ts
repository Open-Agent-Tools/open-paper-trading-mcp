export interface AccountInfo {
  owner: string;
  cash_balance: number;
}

export interface AccountSummary {
  id: string;
  owner: string;
  created_at: string;
  starting_balance: number;
  current_balance: number;
  balance_change: number;
  balance_change_percent: number;
}

export interface AccountsResponse {
  success: boolean;
  accounts: AccountSummary[];
  summary: {
    total_count: number;
    total_starting_balance: number;
    total_current_balance: number;
    total_balance_change: number;
  };
  message: string;
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
