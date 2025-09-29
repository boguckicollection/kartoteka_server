let token: string | null = null;

export const storeAuthToken = async (newToken: string): Promise<void> => {
  token = newToken;
};

export const getAuthToken = () => token;
