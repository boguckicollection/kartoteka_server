import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { router, usePathname } from 'expo-router';
import { clearAuthToken, getAuthToken, storeAuthToken } from '../utils/authToken';

export type AuthContextValue = {
  token: string | null;
  isLoggedIn: boolean;
  isLoading: boolean;
  signIn: (newToken: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshAuthState: () => Promise<string | null>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const pathname = usePathname();

  const refreshAuthState = useCallback(async () => {
    setIsLoading(true);
    try {
      const storedToken = await getAuthToken({ forceRefresh: true });
      setToken(storedToken);
      return storedToken;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshAuthState();
  }, [refreshAuthState]);

  const signIn = useCallback(async (newToken: string) => {
    await storeAuthToken(newToken);
    setToken(newToken);
  }, []);

  const signOut = useCallback(async () => {
    await clearAuthToken();
    setToken(null);
  }, []);

  useEffect(() => {
    if (isLoading) {
      return;
    }

    if (!pathname) {
      return;
    }

    const isAuthRoute = pathname.startsWith('/auth');

    if (!token && !isAuthRoute) {
      router.replace('/auth');
    } else if (token && isAuthRoute) {
      router.replace('/home');
    }
  }, [isLoading, pathname, token]);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      isLoggedIn: Boolean(token),
      isLoading,
      signIn,
      signOut,
      refreshAuthState,
    }),
    [isLoading, refreshAuthState, signIn, signOut, token]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
