
import React, { useState } from 'react';
import { Text, View, TouchableOpacity, ScrollView, Image } from 'react-native';
import { commonStyles, colors } from '../styles/commonStyles';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import Icon from '../components/Icon';
import SimpleBottomSheet from '../components/BottomSheet';

export default function HomeScreen() {
  const [isMenuVisible, setIsMenuVisible] = useState(false);

  const stats = {
    totalCards: 1247,
    totalValue: 15420,
    rareCards: 89,
    activeUsers: 12543,
  };

  const popularCards = [
    { id: 1, name: 'Charizard VMAX', price: 450, image: 'https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=200&h=280&fit=crop' },
    { id: 2, name: 'Pikachu Gold', price: 320, image: 'https://images.unsplash.com/photo-1613771404721-1f92d799e49f?w=200&h=280&fit=crop' },
    { id: 3, name: 'Lugia Legend', price: 280, image: 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=200&h=280&fit=crop' },
  ];

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
        <Text style={[commonStyles.subtitle, { margin: 0 }]}>Pokemon TCG</Text>
        <TouchableOpacity onPress={() => setIsMenuVisible(true)}>
          <Icon name="menu" size={24} color={colors.text} />
        </TouchableOpacity>
      </View>

      <ScrollView style={commonStyles.content}>
        {/* Welcome Section */}
        <View style={commonStyles.section}>
          <Text style={commonStyles.title}>Welcome Back!</Text>
          <Text style={commonStyles.textLight}>Discover and collect your favorite Pokemon cards</Text>
        </View>

        {/* Stats Cards */}
        <View style={commonStyles.section}>
          <Text style={commonStyles.subtitle}>Your Collection</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' }}>
            <View style={[commonStyles.card, { width: '48%', alignItems: 'center' }]}>
              <Text style={[commonStyles.title, { fontSize: 24, margin: 0, color: colors.primary }]}>
                {stats.totalCards}
              </Text>
              <Text style={commonStyles.textLight}>Total Cards</Text>
            </View>
            <View style={[commonStyles.card, { width: '48%', alignItems: 'center' }]}>
              <Text style={[commonStyles.title, { fontSize: 24, margin: 0, color: colors.secondary }]}>
                ${stats.totalValue}
              </Text>
              <Text style={commonStyles.textLight}>Collection Value</Text>
            </View>
          </View>
        </View>

        {/* Popular Cards */}
        <View style={commonStyles.section}>
          <Text style={commonStyles.subtitle}>Popular Cards</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            {popularCards.map((card) => (
              <TouchableOpacity
                key={card.id}
                style={[commonStyles.card, { width: 160, marginRight: 12 }]}
                onPress={() => console.log('Card pressed:', card.name)}
              >
                <Image
                  source={{ uri: card.image }}
                  style={{ width: '100%', height: 120, borderRadius: 8, marginBottom: 8 }}
                  resizeMode="cover"
                />
                <Text style={[commonStyles.text, { fontSize: 14, fontWeight: '600', margin: 0 }]}>
                  {card.name}
                </Text>
                <Text style={[commonStyles.textLight, { fontSize: 12 }]}>
                  ${card.price}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        {/* Quick Actions */}
        <View style={commonStyles.section}>
          <Text style={commonStyles.subtitle}>Quick Actions</Text>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <TouchableOpacity
              style={[commonStyles.card, { width: '48%', alignItems: 'center', paddingVertical: 24 }]}
              onPress={() => router.push('/search')}
            >
              <Icon name="search" size={32} color={colors.primary} />
              <Text style={[commonStyles.text, { marginTop: 8, margin: 0 }]}>Search Cards</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[commonStyles.card, { width: '48%', alignItems: 'center', paddingVertical: 24 }]}
              onPress={() => router.push('/collection')}
            >
              <Icon name="library" size={32} color={colors.secondary} />
              <Text style={[commonStyles.text, { marginTop: 8, margin: 0 }]}>My Collection</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Advertisement Space */}
        <View style={commonStyles.section}>
          <View style={[commonStyles.card, {
            backgroundColor: colors.accent,
            alignItems: 'center',
            paddingVertical: 32,
          }]}>
            <Text style={[commonStyles.subtitle, { color: colors.primary, margin: 0 }]}>
              Special Offer!
            </Text>
            <Text style={[commonStyles.textLight, { color: colors.primary, textAlign: 'center' }]}>
              Get 20% off premium features this month
            </Text>
          </View>
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
          <Icon name="home" size={24} color={colors.primary} />
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
          <Icon name="person" size={24} color={colors.text} />
          <Text style={[commonStyles.textLight, { fontSize: 12, marginTop: 4 }]}>Profile</Text>
        </TouchableOpacity>
      </View>

      {/* Menu Bottom Sheet */}
      <SimpleBottomSheet
        isVisible={isMenuVisible}
        onClose={() => setIsMenuVisible(false)}
      >
        <View style={{ padding: 20 }}>
          <Text style={[commonStyles.subtitle, { textAlign: 'center', marginBottom: 24 }]}>Menu</Text>
          
          <TouchableOpacity
            style={[commonStyles.row, { paddingVertical: 16 }]}
            onPress={() => {
              setIsMenuVisible(false);
              router.push('/profile');
            }}
          >
            <Icon name="person" size={24} color={colors.text} />
            <Text style={[commonStyles.text, { marginLeft: 16, margin: 0 }]}>Profile Settings</Text>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={[commonStyles.row, { paddingVertical: 16 }]}
            onPress={() => {
              setIsMenuVisible(false);
              console.log('Logout pressed');
              router.replace('/auth');
            }}
          >
            <Icon name="log-out" size={24} color={colors.error} />
            <Text style={[commonStyles.text, { marginLeft: 16, margin: 0, color: colors.error }]}>Logout</Text>
          </TouchableOpacity>
        </View>
      </SimpleBottomSheet>
    </SafeAreaView>
  );
}
