import { useState, useEffect, useCallback } from 'react';
import type { SystemHealth } from '../types';
import { checkSystemHealth } from '../services/healthService';

interface UseHealthMonitorOptions {
  interval?: number; // Polling interval in milliseconds
  enabled?: boolean; // Whether to enable polling
}

interface UseHealthMonitorReturn {
  health: SystemHealth | null;
  loading: boolean;
  error: string | null;
  lastChecked: Date | null;
  refresh: () => Promise<void>;
}

/**
 * Custom hook for monitoring system health
 */
export const useHealthMonitor = (
  options: UseHealthMonitorOptions = {}
): UseHealthMonitorReturn => {
  const { interval = 30000, enabled = true } = options; // Default 30 second polling

  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const healthData = await checkSystemHealth();
      setHealth(healthData);
      setLastChecked(new Date());
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      console.error('Health check failed:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial health check
  useEffect(() => {
    if (enabled) {
      refresh();
    }
  }, [enabled, refresh]);

  // Set up polling interval
  useEffect(() => {
    if (!enabled || !interval) return;

    const intervalId = setInterval(refresh, interval);
    return () => clearInterval(intervalId);
  }, [enabled, interval, refresh]);

  return {
    health,
    loading,
    error,
    lastChecked,
    refresh,
  };
};

export default useHealthMonitor;