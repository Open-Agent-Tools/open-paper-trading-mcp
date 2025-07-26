import axios from 'axios';
import type { NewOrder } from '../types';

const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getAccountInfo = async () => {
  const response = await apiClient.get('/account/info');
  return response.data;
};

export const getPortfolioSummary = async () => {
  const response = await apiClient.get('/portfolio/summary');
  return response.data;
};

export const getPositions = async () => {
  const response = await apiClient.get('/portfolio/positions');
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

export default apiClient;
