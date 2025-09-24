import React, { useState } from 'react';
import { Redirect } from 'expo-router';

export default function Index() {
  // Check if user is logged in (for now, we'll redirect to auth)
  const [isLoggedIn] = useState(false);
  
  if (isLoggedIn) {
    return <Redirect href="/home" />;
  }
  
  return <Redirect href="/auth" />;
}
