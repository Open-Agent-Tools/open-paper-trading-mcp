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
