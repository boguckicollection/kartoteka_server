
import React, { useState } from 'react';
import { Text, View, TouchableOpacity, ScrollView, Image, FlatList } from 'react-native';
import { commonStyles, colors } from '../styles/commonStyles';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import Icon from '../components/Icon';
import SimpleBottomSheet from '../components/BottomSheet';

export default function CollectionScreen() {
  const [selectedTab, setSelectedTab] = useState('cards');
  const [isStatsVisible, setIsStatsVisible] = useState(false);

  const myCards = [
    { id: 1, name: 'Charizard VMAX', set: 'Champion\'s Path', price: 450, quantity: 2, condition: 'Near Mint', image: 'https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=200&h=280&fit=crop' },
    { id: 2, name: 'Pikachu VMAX', set: 'Vivid Voltage', price: 320, quantity: 1, condition: 'Mint', image: 'https://images.unsplash.com/photo-1613771404721-1f92d799e49f?w=200&h=280&fit=crop' },
    { id: 3, name: 'Lugia VSTAR', set: 'Silver Tempest', price: 280, quantity: 3, condition: 'Near Mint', image: 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=200&h=280&fit=crop' },
  ];

  const collectionStats = {
    totalCards: 247,
    totalValue: 15420,
    rareCards: 89,
    sets: 45,
    avgCardValue: 62.43,
    topCard: 'Charizard VMAX',
  };

  const priceHistory = [
    { date: '2024-01', value: 12500 },
    { date: '2024-02', value: 13200 },
    { date: '2024-03', value: 14800 },
    { date: '2024-04', value: 15420 },
  ];

  const renderCard = ({ item }: { item: typeof myCards[0] }) => (
    <TouchableOpacity
      style={[commonStyles.card, { marginHorizontal: 10, marginVertical: 8 }]}
      onPress={() => console.log('Card details:', item.name)}
    >
      <View style={commonStyles.row}>
        <Image
          source={{ uri: item.image }}
          style={{ width: 80, height: 112, borderRadius: 8, marginRight: 16 }}
          resizeMode="cover"
        />
        <View style={{ flex: 1 }}>
          <Text style={[commonStyles.text, { fontWeight: '600', margin: 0 }]}>
            {item.name}
          </Text>
          <Text style={[commonStyles.textLight, { fontSize: 14 }]}>
            {item.set}
          </Text>
          <Text style={[commonStyles.textLight, { fontSize: 14 }]}>
            Condition: {item.condition}
          </Text>
          <Text style={[commonStyles.textLight, { fontSize: 14 }]}>
            Quantity: {item.quantity}
          </Text>
          <Text style={[commonStyles.text, { fontWeight: '600', color: colors.primary, marginTop: 4, margin: 0 }]}>
            ${item.price} each
          </Text>
        </View>
        <View style={{ alignItems: 'flex-end' }}>
          <Text style={[commonStyles.text, { fontWeight: '600', color: colors.success, margin: 0 }]}>
            ${item.price * item.quantity}
          </Text>
          <Text style={[commonStyles.textLight, { fontSize: 12 }]}>
            Total Value
          </Text>
        </View>
      </View>
    </TouchableOpacity>
  );

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
        <Text style={[commonStyles.subtitle, { margin: 0 }]}>My Collection</Text>
        <TouchableOpacity onPress={() => setIsStatsVisible(true)}>
          <Icon name="stats-chart" size={24} color={colors.text} />
        </TouchableOpacity>
      </View>

      {/* Tab Navigation */}
      <View style={{
        flexDirection: 'row',
        backgroundColor: colors.backgroundAlt,
        paddingHorizontal: 20,
        paddingVertical: 12,
      }}>
        <TouchableOpacity
          style={{
            flex: 1,
            alignItems: 'center',
            paddingVertical: 8,
            borderBottomWidth: 2,
            borderBottomColor: selectedTab === 'cards' ? colors.primary : 'transparent',
          }}
          onPress={() => setSelectedTab('cards')}
        >
          <Text style={{
            color: selectedTab === 'cards' ? colors.primary : colors.textLight,
            fontWeight: '600',
          }}>
            Cards ({myCards.length})
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={{
            flex: 1,
            alignItems: 'center',
            paddingVertical: 8,
            borderBottomWidth: 2,
            borderBottomColor: selectedTab === 'value' ? colors.primary : 'transparent',
          }}
          onPress={() => setSelectedTab('value')}
        >
          <Text style={{
            color: selectedTab === 'value' ? colors.primary : colors.textLight,
            fontWeight: '600',
          }}>
            Value Tracker
          </Text>
        </TouchableOpacity>
      </View>

      <View style={{ flex: 1 }}>
        {selectedTab === 'cards' ? (
          <>
            {/* Collection Summary */}
            <View style={commonStyles.section}>
              <View style={[commonStyles.card, { backgroundColor: colors.primary }]}>
                <View style={commonStyles.row}>
                  <View style={{ flex: 1 }}>
                    <Text style={[commonStyles.title, { color: colors.backgroundAlt, fontSize: 32, margin: 0 }]}>
                      ${collectionStats.totalValue.toLocaleString()}
                    </Text>
                    <Text style={[commonStyles.textLight, { color: colors.backgroundAlt }]}>
                      Total Collection Value
                    </Text>
                  </View>
                  <View style={{ alignItems: 'flex-end' }}>
                    <Text style={[commonStyles.text, { color: colors.secondary, fontWeight: '600', margin: 0 }]}>
                      {collectionStats.totalCards} cards
                    </Text>
                    <Text style={[commonStyles.textLight, { color: colors.backgroundAlt, fontSize: 12 }]}>
                      {collectionStats.sets} different sets
                    </Text>
                  </View>
                </View>
              </View>
            </View>

            {/* Cards List */}
            <View style={{ flex: 1, paddingHorizontal: 10 }}>
              <FlatList
                data={myCards}
                renderItem={renderCard}
                keyExtractor={(item) => item.id.toString()}
                showsVerticalScrollIndicator={false}
                contentContainerStyle={{ paddingBottom: 100 }}
              />
            </View>
          </>
        ) : (
          <ScrollView style={{ flex: 1 }}>
            {/* Value Overview */}
            <View style={commonStyles.section}>
              <Text style={commonStyles.subtitle}>Portfolio Performance</Text>
              <View style={[commonStyles.card, { alignItems: 'center', paddingVertical: 32 }]}>
                <Text style={[commonStyles.title, { color: colors.success, fontSize: 36, margin: 0 }]}>
                  +23.4%
                </Text>
                <Text style={commonStyles.textLight}>Growth this month</Text>
              </View>
            </View>

            {/* Price History */}
            <View style={commonStyles.section}>
              <Text style={commonStyles.subtitle}>Value History</Text>
              {priceHistory.map((entry, index) => (
                <View key={entry.date} style={[commonStyles.card, commonStyles.row]}>
                  <Text style={[commonStyles.text, { margin: 0 }]}>{entry.date}</Text>
                  <Text style={[commonStyles.text, { fontWeight: '600', color: colors.primary, margin: 0 }]}>
                    ${entry.value.toLocaleString()}
                  </Text>
                </View>
              ))}
            </View>

            {/* Top Performers */}
            <View style={commonStyles.section}>
              <Text style={commonStyles.subtitle}>Top Performers</Text>
              <View style={[commonStyles.card, commonStyles.row]}>
                <View>
                  <Text style={[commonStyles.text, { fontWeight: '600', margin: 0 }]}>
                    {collectionStats.topCard}
                  </Text>
                  <Text style={commonStyles.textLight}>Highest value card</Text>
                </View>
                <Text style={[commonStyles.text, { fontWeight: '600', color: colors.success, margin: 0 }]}>
                  $450
                </Text>
              </View>
            </View>
          </ScrollView>
        )}
      </View>

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
          <Icon name="library" size={24} color={colors.primary} />
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

      {/* Stats Bottom Sheet */}
      <SimpleBottomSheet
        isVisible={isStatsVisible}
        onClose={() => setIsStatsVisible(false)}
      >
        <View style={{ padding: 20 }}>
          <Text style={[commonStyles.subtitle, { textAlign: 'center', marginBottom: 24 }]}>
            Collection Statistics
          </Text>
          
          <View style={[commonStyles.card, { marginBottom: 16 }]}>
            <View style={[commonStyles.row, { marginBottom: 12 }]}>
              <Text style={commonStyles.text}>Total Cards:</Text>
              <Text style={[commonStyles.text, { fontWeight: '600' }]}>
                {collectionStats.totalCards}
              </Text>
            </View>
            <View style={[commonStyles.row, { marginBottom: 12 }]}>
              <Text style={commonStyles.text}>Rare Cards:</Text>
              <Text style={[commonStyles.text, { fontWeight: '600', color: colors.secondary }]}>
                {collectionStats.rareCards}
              </Text>
            </View>
            <View style={[commonStyles.row, { marginBottom: 12 }]}>
              <Text style={commonStyles.text}>Average Card Value:</Text>
              <Text style={[commonStyles.text, { fontWeight: '600', color: colors.primary }]}>
                ${collectionStats.avgCardValue}
              </Text>
            </View>
            <View style={commonStyles.row}>
              <Text style={commonStyles.text}>Different Sets:</Text>
              <Text style={[commonStyles.text, { fontWeight: '600' }]}>
                {collectionStats.sets}
              </Text>
            </View>
          </View>
        </View>
      </SimpleBottomSheet>
    </SafeAreaView>
  );
}
