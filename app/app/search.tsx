
import React, { useState } from 'react';
import { Text, View, TextInput, TouchableOpacity, ScrollView, Image, FlatList } from 'react-native';
import { commonStyles, colors } from '../styles/commonStyles';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import Icon from '../components/Icon';

export default function SearchScreen() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFilter, setSelectedFilter] = useState('all');

  const mockCards = [
    { id: 1, name: 'Charizard VMAX', set: 'Champion\'s Path', price: 450, rarity: 'Secret Rare', image: 'https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=200&h=280&fit=crop' },
    { id: 2, name: 'Pikachu VMAX', set: 'Vivid Voltage', price: 320, rarity: 'Rainbow Rare', image: 'https://images.unsplash.com/photo-1613771404721-1f92d799e49f?w=200&h=280&fit=crop' },
    { id: 3, name: 'Lugia VSTAR', set: 'Silver Tempest', price: 280, rarity: 'Ultra Rare', image: 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=200&h=280&fit=crop' },
    { id: 4, name: 'Rayquaza VMAX', set: 'Evolving Skies', price: 380, rarity: 'Secret Rare', image: 'https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=200&h=280&fit=crop' },
    { id: 5, name: 'Mew VMAX', set: 'Fusion Strike', price: 220, rarity: 'Ultra Rare', image: 'https://images.unsplash.com/photo-1613771404721-1f92d799e49f?w=200&h=280&fit=crop' },
    { id: 6, name: 'Arceus VSTAR', set: 'Brilliant Stars', price: 180, rarity: 'Ultra Rare', image: 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=200&h=280&fit=crop' },
  ];

  const filters = [
    { id: 'all', name: 'All Cards' },
    { id: 'rare', name: 'Rare' },
    { id: 'ultra', name: 'Ultra Rare' },
    { id: 'secret', name: 'Secret Rare' },
  ];

  const filteredCards = mockCards.filter(card => {
    const matchesSearch = card.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter = selectedFilter === 'all' || 
      (selectedFilter === 'rare' && card.rarity.includes('Rare')) ||
      (selectedFilter === 'ultra' && card.rarity.includes('Ultra')) ||
      (selectedFilter === 'secret' && card.rarity.includes('Secret'));
    
    return matchesSearch && matchesFilter;
  });

  const renderCard = ({ item }: { item: typeof mockCards[0] }) => (
    <TouchableOpacity
      style={[commonStyles.card, { marginHorizontal: 10, marginVertical: 8 }]}
      onPress={() => console.log('Card selected:', item.name)}
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
            {item.rarity}
          </Text>
          <Text style={[commonStyles.text, { fontWeight: '600', color: colors.primary, marginTop: 8, margin: 0 }]}>
            ${item.price}
          </Text>
        </View>
        <TouchableOpacity
          style={{
            backgroundColor: colors.secondary,
            paddingHorizontal: 16,
            paddingVertical: 8,
            borderRadius: 6,
          }}
          onPress={() => console.log('Add to collection:', item.name)}
        >
          <Text style={{ color: colors.primary, fontWeight: '600' }}>Add</Text>
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={commonStyles.container}>
      {/* Header */}
      <View style={{
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 20,
        paddingVertical: 16,
        backgroundColor: colors.backgroundAlt,
        borderBottomWidth: 1,
        borderBottomColor: colors.grey,
      }}>
        <TouchableOpacity onPress={() => router.back()}>
          <Icon name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[commonStyles.subtitle, { marginLeft: 16, margin: 0 }]}>Search Cards</Text>
      </View>

      <View style={{ flex: 1 }}>
        {/* Search Input */}
        <View style={commonStyles.section}>
          <View style={{
            flexDirection: 'row',
            alignItems: 'center',
            backgroundColor: colors.backgroundAlt,
            borderRadius: 8,
            paddingHorizontal: 16,
            borderWidth: 1,
            borderColor: colors.grey,
          }}>
            <Icon name="search" size={20} color={colors.textLight} />
            <TextInput
              style={{
                flex: 1,
                paddingVertical: 12,
                paddingHorizontal: 12,
                fontSize: 16,
                color: colors.text,
              }}
              placeholder="Search for Pokemon cards..."
              placeholderTextColor={colors.textLight}
              value={searchQuery}
              onChangeText={setSearchQuery}
            />
          </View>
        </View>

        {/* Filters */}
        <View style={[commonStyles.section, { marginBottom: 16 }]}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            {filters.map((filter) => (
              <TouchableOpacity
                key={filter.id}
                style={{
                  backgroundColor: selectedFilter === filter.id ? colors.primary : colors.backgroundAlt,
                  paddingHorizontal: 16,
                  paddingVertical: 8,
                  borderRadius: 20,
                  marginRight: 12,
                  borderWidth: 1,
                  borderColor: selectedFilter === filter.id ? colors.primary : colors.grey,
                }}
                onPress={() => setSelectedFilter(filter.id)}
              >
                <Text style={{
                  color: selectedFilter === filter.id ? colors.backgroundAlt : colors.text,
                  fontWeight: '500',
                }}>
                  {filter.name}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        {/* Results */}
        <View style={{ flex: 1, paddingHorizontal: 10 }}>
          <Text style={[commonStyles.textLight, { paddingHorizontal: 10, marginBottom: 16 }]}>
            {filteredCards.length} cards found
          </Text>
          
          <FlatList
            data={filteredCards}
            renderItem={renderCard}
            keyExtractor={(item) => item.id.toString()}
            showsVerticalScrollIndicator={false}
            contentContainerStyle={{ paddingBottom: 100 }}
          />
        </View>
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
          <Icon name="search" size={24} color={colors.primary} />
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
    </SafeAreaView>
  );
}
