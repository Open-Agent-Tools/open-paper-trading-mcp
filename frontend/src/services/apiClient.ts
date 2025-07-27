import axios from 'axios';
import type { 
  NewOrder, 
  StockSearchResponse, 
  StockInfoResponse, 
  MarketHoursResponse, 
  StockPriceResponse,
  PriceHistoryResponse,
  StockRatingsResponse,
  StockEventsResponse,
  OptionsChainResponse,
  OptionGreeksResponse,
  StockOrdersResponse,
  OptionsOrdersResponse
} from '../types';

export interface CreateAccountData {
  owner: string;
  starting_balance: number;
}

const apiClient = axios.create({
  baseURL: '/api/v1/trading',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getAllAccounts = async () => {
  const response = await apiClient.get('/accounts');
  return response.data;
};

export const createAccount = async (accountData: CreateAccountData) => {
  const response = await apiClient.post('/accounts', accountData);
  return response.data;
};

export const getAccountInfo = async () => {
  const response = await apiClient.get('/account/info');
  return response.data;
};

export const getPortfolioSummary = async () => {
  const response = await apiClient.get('/portfolio/summary');
  return response.data;
};

export const getPositions = async () => {
  const response = await apiClient.get('/positions');
  return response.data;
};

export const createOrder = async (order: NewOrder) => {
  const response = await apiClient.post('/orders', order);
  return response.data;
};

export const getOrders = async () => {
  const response = await apiClient.get('/orders');
  return response.data;
};

export const cancelOrder = async (orderId: string) => {
  const response = await apiClient.delete(`/orders/${orderId}`);
  return response.data;
};

// Market Data API functions
export const searchStocks = async (query: string): Promise<StockSearchResponse> => {
  const response = await apiClient.get(`/stocks/search`, {
    params: { query }
  });
  return response.data;
};

export const getStockInfo = async (symbol: string): Promise<StockInfoResponse> => {
  const response = await apiClient.get(`/stock/info/${symbol}`);
  return response.data;
};

export const getMarketHours = async (): Promise<MarketHoursResponse> => {
  const response = await apiClient.get('/market/hours');
  return response.data;
};

export const getStockPrice = async (symbol: string): Promise<StockPriceResponse> => {
  const response = await apiClient.get(`/stock/price/${symbol}`);
  return response.data;
};

// Additional Market Data API functions
export const getPriceHistory = async (symbol: string, period: string = 'week'): Promise<PriceHistoryResponse> => {
  const response = await apiClient.get(`/stock/history/${symbol}`, {
    params: { period }
  });
  return response.data;
};

export const getStockRatings = async (symbol: string): Promise<StockRatingsResponse> => {
  const response = await apiClient.get(`/stock/ratings/${symbol}`);
  return response.data;
};

export const getStockEvents = async (symbol: string): Promise<StockEventsResponse> => {
  const response = await apiClient.get(`/stock/events/${symbol}`);
  return response.data;
};

// Options API functions
export const getOptionsChain = async (underlying: string, expirationDate?: string): Promise<OptionsChainResponse> => {
  const response = await apiClient.get(`/options/chain/${underlying}`, {
    params: expirationDate ? { expiration_date: expirationDate } : {}
  });
  return response.data;
};

export const getOptionGreeks = async (optionSymbol: string, underlyingPrice?: number): Promise<OptionGreeksResponse> => {
  const response = await apiClient.get(`/options/greeks/${optionSymbol}`, {
    params: underlyingPrice ? { underlying_price: underlyingPrice } : {}
  });
  return response.data;
};

export const getOptionExpirations = async (underlying: string) => {
  const response = await apiClient.get(`/options/expirations/${underlying}`);
  return response.data;
};

export const getOptionStrikes = async (underlying: string, expirationDate?: string, optionType?: string) => {
  const response = await apiClient.get(`/options/strikes/${underlying}`, {
    params: {
      ...(expirationDate && { expiration_date: expirationDate }),
      ...(optionType && { option_type: optionType })
    }
  });
  return response.data;
};

// Order History API functions
export const getStockOrders = async (): Promise<StockOrdersResponse> => {
  const response = await apiClient.get('/orders/stocks');
  return response.data;
};

export const getOptionsOrders = async (): Promise<OptionsOrdersResponse> => {
  const response = await apiClient.get('/orders/options');
  return response.data;
};

export default apiClient;
