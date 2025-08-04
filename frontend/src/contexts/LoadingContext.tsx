import React, { createContext, useContext, useState, useCallback } from 'react';
import type { ReactNode } from 'react';

interface LoadingState {
  [key: string]: boolean;
}

interface LoadingContextType {
  loadingStates: LoadingState;
  setLoading: (key: string, loading: boolean) => void;
  clearLoading: (key: string) => void;
  isAnyLoading: () => boolean;
  isLoading: (key: string) => boolean;
  getLoadingKeys: () => string[];
}

const LoadingContext = createContext<LoadingContextType | undefined>(undefined);

interface LoadingProviderProps {
  children: ReactNode;
}

export const LoadingProvider: React.FC<LoadingProviderProps> = ({ children }) => {
  const [loadingStates, setLoadingStates] = useState<LoadingState>({});

  const setLoading = useCallback((key: string, loading: boolean) => {
    setLoadingStates(prev => ({
      ...prev,
      [key]: loading
    }));
  }, []);

  const clearLoading = useCallback((key: string) => {
    setLoadingStates(prev => {
      const newState = { ...prev };
      delete newState[key];
      return newState;
    });
  }, []);

  const isAnyLoading = (): boolean => {
    return Object.values(loadingStates).some(loading => loading);
  };

  const isLoading = (key: string): boolean => {
    return loadingStates[key] || false;
  };

  const getLoadingKeys = (): string[] => {
    return Object.keys(loadingStates).filter(key => loadingStates[key]);
  };

  const value: LoadingContextType = {
    loadingStates,
    setLoading,
    clearLoading,
    isAnyLoading,
    isLoading,
    getLoadingKeys
  };

  return (
    <LoadingContext.Provider value={value}>
      {children}
    </LoadingContext.Provider>
  );
};

export const useLoading = (): LoadingContextType => {
  const context = useContext(LoadingContext);
  if (!context) {
    throw new Error('useLoading must be used within a LoadingProvider');
  }
  return context;
};

// Hook for managing individual component loading states
export const useComponentLoading = (componentKey: string) => {
  const { setLoading, isLoading, clearLoading } = useLoading();

  const startLoading = useCallback(() => setLoading(componentKey, true), [setLoading, componentKey]);
  const stopLoading = useCallback(() => setLoading(componentKey, false), [setLoading, componentKey]);
  const clear = useCallback(() => clearLoading(componentKey), [clearLoading, componentKey]);
  const loading = isLoading(componentKey);

  return {
    loading,
    startLoading,
    stopLoading,
    clear
  };
};