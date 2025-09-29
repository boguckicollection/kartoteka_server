import React, { useEffect } from 'react';
import { Redirect } from 'expo-router';
import { useAuth } from '../context/AuthContext';

export default function Index() {
  const { isLoggedIn, isLoading, refreshAuthState } = useAuth();

  useEffect(() => {
    refreshAuthState();
  }, [refreshAuthState]);

  if (isLoading) {
    return null;
  }

  if (isLoggedIn) {
    return <Redirect href="/home" />;
  }

  return <Redirect href="/auth" />;
}
