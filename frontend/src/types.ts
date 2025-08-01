// Re-export account types for backwards compatibility
export type {
  AccountInfo,
  AccountSummary,
  AccountsResponse,
  CreateAccountRequest,
  CreateAccountResponse,
  DeleteAccountResponse,
  AccountBalance,
  AccountType,
  AccountFormData,
  AccountFormErrors,
} from './types/account';

export interface Position {
  symbol: string;
  quantity: number;
  avg_price: number;
  current_price: number | null;
  market_value: number | null;
  cost_basis?: number;
  unrealized_pnl: number | null;
  unrealized_pnl_percent?: number | null;
  realized_pnl?: number;
  asset_type?: string;
  side?: string;
  
  // Options-specific fields
  option_type: string | null;
  strike: number | null;
  expiration_date: string | null;
  underlying_symbol: string | null;
  
  // Greeks (for options positions)
  delta?: number | null;
  gamma?: number | null;
  theta?: number | null;
  vega?: number | null;
  rho?: number | null;
  iv?: number | null;
}

export type OrderType = 'buy' | 'sell' | 'buy_to_open' | 'sell_to_open' | 'buy_to_close' | 'sell_to_close' | 'stop_loss' | 'stop_limit' | 'trailing_stop';

export type OrderCondition = 'market' | 'limit' | 'stop' | 'stop_limit';

export type OrderStatus = 'pending' | 'triggered' | 'filled' | 'cancelled' | 'rejected' | 'partially_filled' | 'expired';

export interface NewOrder {
  symbol: string;
  order_type: OrderType;
  quantity: number;
  condition: OrderCondition;
  price?: number;
  stop_price?: number;
  trail_percent?: number;
  trail_amount?: number;
  account_id?: string;
}

export interface Order {
  id: string;
  symbol: string;
  quantity: number;
  order_type: OrderType;
  condition: OrderCondition;
  price?: number;
  stop_price?: number;
  status: OrderStatus;
  created_at?: string;
  filled_at?: string;
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

// Market Data Types
export interface StockSearchResult {
  symbol: string;
  name: string;
  tradeable: boolean;
}

export interface StockSearchResponse {
  success: boolean;
  query: string;
  results: {
    query: string;
    results: StockSearchResult[];
  };
  message: string;
}

export interface StockInfo {
  symbol: string;
  company_name: string;
  sector: string;
  industry: string;
  description: string;
  market_cap: string;
  pe_ratio: string;
  dividend_yield: string;
  high_52_weeks: string;
  low_52_weeks: string;
  average_volume: string;
  tradeable: boolean;
}

export interface StockInfoResponse {
  success: boolean;
  symbol: string;
  info: StockInfo;
  message: string;
}

export interface MarketHours {
  is_open: boolean;
  opens_at: string;
  closes_at: string;
}

export interface MarketHoursResponse {
  success: boolean;
  market_hours: MarketHours;
  message: string;
}

export interface StockPriceData {
  symbol?: string;
  price?: number;
  change?: number;
  change_percent?: number;
  volume?: number;
  high?: number;
  low?: number;
  open?: number;
  previous_close?: number;
  error?: string;
}

export interface StockPriceResponse {
  success: boolean;
  symbol: string;
  price_data: StockPriceData;
  message: string;
}

// Price History Types
export interface PriceHistoryPoint {
  timestamp?: string;
  date?: string; // API uses 'date' instead of 'timestamp'
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PriceHistoryData {
  symbol: string;
  period: string;
  interval?: string; // API includes interval field
  points?: PriceHistoryPoint[]; // Frontend expects 'points'
  data_points?: PriceHistoryPoint[]; // API returns 'data_points'
}

export interface PriceHistoryResponse {
  success: boolean;
  symbol: string;
  period: string;
  history: PriceHistoryData;
  message: string;
}

// Analyst Ratings Types
export interface AnalystRating {
  rating: string;
  target_price: number;
  firm: string;
  date: string;
}

export interface StockRatingsData {
  symbol: string;
  overall_rating: string;
  rating_score: number;
  analyst_count: number;
  ratings_breakdown: {
    strong_buy: number;
    buy: number;
    hold: number;
    sell: number;
    strong_sell: number;
  };
  price_targets: {
    average_target: number;
    high_target: number;
    low_target: number;
    median_target: number;
  };
  last_updated: string;
  message?: string;
  // Legacy fields for backwards compatibility
  summary?: {
    buy: number;
    hold: number;
    sell: number;
    average_rating: string;
    target_price: number;
  };
  ratings?: AnalystRating[];
}

export interface StockRatingsResponse {
  success: boolean;
  symbol: string;
  ratings: StockRatingsData;
  message: string;
}

// Corporate Events Types
export interface CorporateEvent {
  type: string;
  date: string;
  amount?: number;
  description: string;
}

export interface StockEventsData {
  symbol: string;
  events: CorporateEvent[];
}

export interface StockEventsResponse {
  success: boolean;
  symbol: string;
  events: StockEventsData;
  message: string;
}

// Options Types
export interface OptionQuote {
  symbol: string;
  strike: number;
  expiration: string;
  price: number | null;
  bid: number;
  ask: number;
  volume: number | null;
  open_interest: number | null;
  implied_volatility: number;
}

export interface OptionsChainData {
  underlying: string;
  expiration_filter?: string;
  chain: {
    calls: OptionQuote[];
    puts: OptionQuote[];
    calls_count: number;
    puts_count: number;
  };
}

export interface OptionsChainResponse {
  success: boolean;
  underlying: string;
  expiration_filter?: string;
  chain: {
    calls: OptionQuote[];
    puts: OptionQuote[];
    calls_count: number;
    puts_count: number;
  };
  message: string;
}

export interface OptionGreeks {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
  iv?: number;
}

export interface OptionGreeksResponse {
  success: boolean;
  option_symbol: string;
  underlying_price?: number;
  greeks: OptionGreeks;
  message: string;
}

// Order History Types
export interface OrderHistoryItem extends Order {
  filled_quantity?: number;
  average_filled_price?: number;
  fees?: number;
  instrument?: string;
  updated_at?: string;
}

export interface StockOrdersResponse {
  success: boolean;
  orders: OrderHistoryItem[];
  count: number;
  message: string;
}

export interface OptionsOrdersResponse {
  success: boolean;
  orders: OrderHistoryItem[];
  count: number;
  message: string;
}
