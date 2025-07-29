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

export interface CreateAccountRequest {
  owner: string;
  starting_balance: number;
  name?: string;
}

export interface CreateAccountResponse {
  success: boolean;
  account_id: string;
  message: string;
}

export interface DeleteAccountResponse {
  success: boolean;
  message: string;
}

export interface AccountBalance {
  success: boolean;
  account_id: string;
  cash_balance: number;
  message: string;
}

export type AccountType = 'individual' | 'joint' | 'corporate' | 'trust';

export interface AccountFormData {
  owner: string;
  name: string;
  startingBalance: string;
  accountType: AccountType;
}

export interface AccountFormErrors {
  owner?: string;
  name?: string;
  startingBalance?: string;
  accountType?: string;
}