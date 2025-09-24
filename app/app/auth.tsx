
import React, { useState } from 'react';
import { Text, View, TextInput, TouchableOpacity, ScrollView, Alert } from 'react-native';
import { commonStyles, colors } from '../styles/commonStyles';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import Icon from '../components/Icon';

export default function AuthScreen() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [username, setUsername] = useState('');

  const handleAuth = () => {
    console.log('Auth attempt:', { isLogin, email, username });
    
    if (!email || !password) {
      Alert.alert('Error', 'Please fill in all required fields');
      return;
    }

    if (!isLogin && password !== confirmPassword) {
      Alert.alert('Error', 'Passwords do not match');
      return;
    }

    // For demo purposes, we'll just navigate to home
    router.replace('/home');
  };

  return (
    <SafeAreaView style={commonStyles.container}>
      <ScrollView style={commonStyles.content} contentContainerStyle={{ flexGrow: 1 }}>
        <View style={commonStyles.section}>
          <View style={{ alignItems: 'center', marginTop: 40, marginBottom: 40 }}>
            <View style={{
              width: 80,
              height: 80,
              backgroundColor: colors.secondary,
              borderRadius: 40,
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 16,
            }}>
              <Icon name="card" size={40} color={colors.primary} />
            </View>
            <Text style={commonStyles.title}>Pokemon TCG Collector</Text>
            <Text style={commonStyles.textLight}>
              {isLogin ? 'Welcome back!' : 'Join the community'}
            </Text>
          </View>

          <View style={commonStyles.card}>
            <Text style={[commonStyles.subtitle, { textAlign: 'center', marginBottom: 24 }]}>
              {isLogin ? 'Sign In' : 'Create Account'}
            </Text>

            {!isLogin && (
              <TextInput
                style={commonStyles.input}
                placeholder="Username"
                placeholderTextColor={colors.textLight}
                value={username}
                onChangeText={setUsername}
                autoCapitalize="none"
              />
            )}

            <TextInput
              style={commonStyles.input}
              placeholder="Email"
              placeholderTextColor={colors.textLight}
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
            />

            <TextInput
              style={commonStyles.input}
              placeholder="Password"
              placeholderTextColor={colors.textLight}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
            />

            {!isLogin && (
              <TextInput
                style={commonStyles.input}
                placeholder="Confirm Password"
                placeholderTextColor={colors.textLight}
                value={confirmPassword}
                onChangeText={setConfirmPassword}
                secureTextEntry
              />
            )}

            <TouchableOpacity
              style={{
                backgroundColor: colors.primary,
                paddingVertical: 16,
                borderRadius: 8,
                alignItems: 'center',
                marginTop: 8,
              }}
              onPress={handleAuth}
            >
              <Text style={{
                color: colors.backgroundAlt,
                fontSize: 16,
                fontWeight: '600',
              }}>
                {isLogin ? 'Sign In' : 'Create Account'}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={{ alignItems: 'center', marginTop: 16 }}
              onPress={() => setIsLogin(!isLogin)}
            >
              <Text style={[commonStyles.textLight, { textAlign: 'center' }]}>
                {isLogin ? "Don't have an account? " : "Already have an account? "}
                <Text style={{ color: colors.primary, fontWeight: '600' }}>
                  {isLogin ? 'Sign Up' : 'Sign In'}
                </Text>
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
