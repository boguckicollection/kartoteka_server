
import React, { useState } from 'react';
import { Text, View, TouchableOpacity, ScrollView, Switch, Alert } from 'react-native';
import { commonStyles, colors } from '../styles/commonStyles';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import Icon from '../components/Icon';
import SimpleBottomSheet from '../components/BottomSheet';

export default function ProfileScreen() {
  const [notificationsEnabled, setNotificationsEnabled] = useState(true);
  const [priceAlertsEnabled, setPriceAlertsEnabled] = useState(true);
  const [isWalletVisible, setIsWalletVisible] = useState(false);

  const userStats = {
    username: 'PokeMaster2024',
    joinDate: 'January 2024',
    totalCards: 247,
    totalValue: 15420,
    wishlistItems: 23,
    walletBalance: 1250,
  };

  const handleLogout = () => {
    Alert.alert(
      'Logout',
      'Are you sure you want to logout?',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Logout', style: 'destructive', onPress: () => router.replace('/auth') },
      ]
    );
  };

  return (
    <SafeAreaView style={commonStyles.container}>
      {/* Header */}
      <View style={{
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 20,
        paddingVertical: 16,
        backgroundColor: colors.backgroundAlt,
        borderBottomWidth: 1,
        borderBottomColor: colors.grey,
      }}>
        <TouchableOpacity onPress={() => router.back()}>
          <Icon name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[commonStyles.subtitle, { margin: 0 }]}>Profile</Text>
        <TouchableOpacity onPress={() => console.log('Edit profile')}>
          <Icon name="create" size={24} color={colors.text} />
        </TouchableOpacity>
      </View>

      <ScrollView style={commonStyles.content}>
        {/* Profile Header */}
        <View style={commonStyles.section}>
          <View style={[commonStyles.card, { alignItems: 'center', paddingVertical: 32 }]}>
            <View style={{
              width: 80,
              height: 80,
              backgroundColor: colors.primary,
              borderRadius: 40,
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 16,
            }}>
              <Icon name="person" size={40} color={colors.backgroundAlt} />
            </View>
            <Text style={[commonStyles.title, { fontSize: 24, margin: 0 }]}>
              {userStats.username}
            </Text>
            <Text style={commonStyles.textLight}>
              Member since {userStats.joinDate}
            </Text>
          </View>
        </View>

        {/* Stats Overview */}
        <View style={commonStyles.section}>
          <Text style={commonStyles.subtitle}>Your Stats</Text>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 16 }}>
            <View style={[commonStyles.card, { width: '48%', alignItems: 'center' }]}>
              <Text style={[commonStyles.title, { fontSize: 24, margin: 0, color: colors.primary }]}>
                {userStats.totalCards}
              </Text>
              <Text style={commonStyles.textLight}>Cards Owned</Text>
            </View>
            <View style={[commonStyles.card, { width: '48%', alignItems: 'center' }]}>
              <Text style={[commonStyles.title, { fontSize: 24, margin: 0, color: colors.secondary }]}>
                ${userStats.totalValue.toLocaleString()}
              </Text>
              <Text style={commonStyles.textLight}>Collection Value</Text>
            </View>
          </View>
          <TouchableOpacity
            style={[commonStyles.card, commonStyles.row]}
            onPress={() => setIsWalletVisible(true)}
          >
            <View>
              <Text style={[commonStyles.text, { fontWeight: '600', margin: 0 }]}>
                Wallet Balance
              </Text>
              <Text style={commonStyles.textLight}>
                Available for purchases
              </Text>
            </View>
            <Text style={[commonStyles.text, { fontWeight: '600', color: colors.success, margin: 0 }]}>
              ${userStats.walletBalance}
            </Text>
          </TouchableOpacity>
        </View>

        {/* Quick Actions */}
        <View style={commonStyles.section}>
          <Text style={commonStyles.subtitle}>Quick Actions</Text>
          <TouchableOpacity
            style={[commonStyles.card, commonStyles.row]}
            onPress={() => console.log('View wishlist')}
          >
            <Icon name="heart" size={24} color={colors.error} />
            <View style={{ flex: 1, marginLeft: 16 }}>
              <Text style={[commonStyles.text, { margin: 0 }]}>Wishlist</Text>
              <Text style={commonStyles.textLight}>
                {userStats.wishlistItems} items
              </Text>
            </View>
            <Icon name="chevron-forward" size={20} color={colors.textLight} />
          </TouchableOpacity>

          <TouchableOpacity
            style={[commonStyles.card, commonStyles.row]}
            onPress={() => console.log('Trading history')}
          >
            <Icon name="swap-horizontal" size={24} color={colors.accent} />
            <View style={{ flex: 1, marginLeft: 16 }}>
              <Text style={[commonStyles.text, { margin: 0 }]}>Trading History</Text>
              <Text style={commonStyles.textLight}>
                View past trades
              </Text>
            </View>
            <Icon name="chevron-forward" size={20} color={colors.textLight} />
          </TouchableOpacity>

          <TouchableOpacity
            style={[commonStyles.card, commonStyles.row]}
            onPress={() => console.log('Price alerts')}
          >
            <Icon name="notifications" size={24} color={colors.warning} />
            <View style={{ flex: 1, marginLeft: 16 }}>
              <Text style={[commonStyles.text, { margin: 0 }]}>Price Alerts</Text>
              <Text style={commonStyles.textLight}>
                Manage your alerts
              </Text>
            </View>
            <Icon name="chevron-forward" size={20} color={colors.textLight} />
          </TouchableOpacity>
        </View>

        {/* Settings */}
        <View style={commonStyles.section}>
          <Text style={commonStyles.subtitle}>Settings</Text>
          
          <View style={[commonStyles.card, commonStyles.row]}>
            <Icon name="notifications" size={24} color={colors.text} />
            <View style={{ flex: 1, marginLeft: 16 }}>
              <Text style={[commonStyles.text, { margin: 0 }]}>Push Notifications</Text>
              <Text style={commonStyles.textLight}>
                Get notified about updates
              </Text>
            </View>
            <Switch
              value={notificationsEnabled}
              onValueChange={setNotificationsEnabled}
              trackColor={{ false: colors.grey, true: colors.primary }}
              thumbColor={colors.backgroundAlt}
            />
          </View>

          <View style={[commonStyles.card, commonStyles.row]}>
            <Icon name="trending-up" size={24} color={colors.text} />
            <View style={{ flex: 1, marginLeft: 16 }}>
              <Text style={[commonStyles.text, { margin: 0 }]}>Price Alerts</Text>
              <Text style={commonStyles.textLight}>
                Get alerts for price changes
              </Text>
            </View>
            <Switch
              value={priceAlertsEnabled}
              onValueChange={setPriceAlertsEnabled}
              trackColor={{ false: colors.grey, true: colors.primary }}
              thumbColor={colors.backgroundAlt}
            />
          </View>

          <TouchableOpacity
            style={[commonStyles.card, commonStyles.row]}
            onPress={() => console.log('Privacy settings')}
          >
            <Icon name="shield-checkmark" size={24} color={colors.text} />
            <View style={{ flex: 1, marginLeft: 16 }}>
              <Text style={[commonStyles.text, { margin: 0 }]}>Privacy & Security</Text>
              <Text style={commonStyles.textLight}>
                Manage your privacy settings
              </Text>
            </View>
            <Icon name="chevron-forward" size={20} color={colors.textLight} />
          </TouchableOpacity>

          <TouchableOpacity
            style={[commonStyles.card, commonStyles.row]}
            onPress={() => console.log('Help & Support')}
          >
            <Icon name="help-circle" size={24} color={colors.text} />
            <View style={{ flex: 1, marginLeft: 16 }}>
              <Text style={[commonStyles.text, { margin: 0 }]}>Help & Support</Text>
              <Text style={commonStyles.textLight}>
                Get help and contact support
              </Text>
            </View>
            <Icon name="chevron-forward" size={20} color={colors.textLight} />
          </TouchableOpacity>
        </View>

        {/* Logout */}
        <View style={commonStyles.section}>
          <TouchableOpacity
            style={[commonStyles.card, { backgroundColor: colors.error, alignItems: 'center' }]}
            onPress={handleLogout}
          >
            <Text style={[commonStyles.text, { color: colors.backgroundAlt, fontWeight: '600', margin: 0 }]}>
              Logout
            </Text>
          </TouchableOpacity>
        </View>
      </ScrollView>

      {/* Bottom Navigation */}
      <View style={{
        flexDirection: 'row',
        backgroundColor: colors.backgroundAlt,
        borderTopWidth: 1,
        borderTopColor: colors.grey,
        paddingVertical: 12,
      }}>
        <TouchableOpacity
          style={{ flex: 1, alignItems: 'center', paddingVertical: 8 }}
          onPress={() => router.push('/home')}
        >
          <Icon name="home" size={24} color={colors.text} />
          <Text style={[commonStyles.textLight, { fontSize: 12, marginTop: 4 }]}>Home</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={{ flex: 1, alignItems: 'center', paddingVertical: 8 }}
          onPress={() => router.push('/search')}
        >
          <Icon name="search" size={24} color={colors.text} />
          <Text style={[commonStyles.textLight, { fontSize: 12, marginTop: 4 }]}>Search</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={{ flex: 1, alignItems: 'center', paddingVertical: 8 }}
          onPress={() => router.push('/collection')}
        >
          <Icon name="library" size={24} color={colors.text} />
          <Text style={[commonStyles.textLight, { fontSize: 12, marginTop: 4 }]}>Collection</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={{ flex: 1, alignItems: 'center', paddingVertical: 8 }}
          onPress={() => router.push('/profile')}
        >
          <Icon name="person" size={24} color={colors.primary} />
          <Text style={[commonStyles.textLight, { fontSize: 12, marginTop: 4 }]}>Profile</Text>
        </TouchableOpacity>
      </View>

      {/* Wallet Bottom Sheet */}
      <SimpleBottomSheet
        isVisible={isWalletVisible}
        onClose={() => setIsWalletVisible(false)}
      >
        <View style={{ padding: 20 }}>
          <Text style={[commonStyles.subtitle, { textAlign: 'center', marginBottom: 24 }]}>
            Wallet
          </Text>
          
          <View style={[commonStyles.card, { alignItems: 'center', paddingVertical: 32, marginBottom: 24 }]}>
            <Text style={[commonStyles.title, { fontSize: 36, margin: 0, color: colors.success }]}>
              ${userStats.walletBalance}
            </Text>
            <Text style={commonStyles.textLight}>Available Balance</Text>
          </View>

          <TouchableOpacity
            style={{
              backgroundColor: colors.primary,
              paddingVertical: 16,
              borderRadius: 8,
              alignItems: 'center',
              marginBottom: 12,
            }}
            onPress={() => console.log('Add funds')}
          >
            <Text style={{
              color: colors.backgroundAlt,
              fontSize: 16,
              fontWeight: '600',
            }}>
              Add Funds
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={{
              backgroundColor: colors.backgroundAlt,
              borderWidth: 1,
              borderColor: colors.primary,
              paddingVertical: 16,
              borderRadius: 8,
              alignItems: 'center',
            }}
            onPress={() => console.log('Transaction history')}
          >
            <Text style={{
              color: colors.primary,
              fontSize: 16,
              fontWeight: '600',
            }}>
              Transaction History
            </Text>
          </TouchableOpacity>
        </View>
      </SimpleBottomSheet>
    </SafeAreaView>
  );
}
