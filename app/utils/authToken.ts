import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

const TOKEN_STORAGE_KEY = 'auth_token';

let cachedToken: string | null | undefined = undefined;

type StorageLike = {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
  removeItem: (key: string) => void;
};

const getWebStorage = (): StorageLike | null => {
  if (typeof globalThis === 'undefined') {
    return null;
  }

  const candidate = (globalThis as Record<string, unknown>).localStorage;
  if (!candidate) {
    return null;
  }

  return candidate as StorageLike;
};

const readTokenFromStorage = async (): Promise<string | null> => {
  if (Platform.OS === 'web') {
    const storage = getWebStorage();
    if (!storage) {
      return null;
    }

    const storedValue = storage.getItem(TOKEN_STORAGE_KEY);
    return storedValue ?? null;
  }

  const isAvailable = await SecureStore.isAvailableAsync();
  if (!isAvailable) {
    return null;
  }

  const storedValue = await SecureStore.getItemAsync(TOKEN_STORAGE_KEY);
  return storedValue ?? null;
};

const persistToken = async (token: string | null) => {
  if (Platform.OS === 'web') {
    const storage = getWebStorage();
    if (!storage) {
      return;
    }

    if (token === null) {
      storage.removeItem(TOKEN_STORAGE_KEY);
    } else {
      storage.setItem(TOKEN_STORAGE_KEY, token);
    }
    return;
  }

  const isAvailable = await SecureStore.isAvailableAsync();
  if (!isAvailable) {
    return;
  }

  if (token === null) {
    await SecureStore.deleteItemAsync(TOKEN_STORAGE_KEY);
  } else {
    await SecureStore.setItemAsync(TOKEN_STORAGE_KEY, token);
  }
};

export const storeAuthToken = async (newToken: string): Promise<void> => {
  cachedToken = newToken;
  await persistToken(newToken);
};

export const getAuthToken = async (
  options: { forceRefresh?: boolean } = {}
): Promise<string | null> => {
  if (!options.forceRefresh && cachedToken !== undefined) {
    return cachedToken;
  }

  const storedToken = await readTokenFromStorage();
  cachedToken = storedToken;
  return storedToken;
};

export const clearAuthToken = async (): Promise<void> => {
  cachedToken = null;
  await persistToken(null);
};
