import React, { useMemo, useState } from 'react';
import {
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Image,
  FlatList,
  Pressable,
  StyleSheet,
} from 'react-native';
import { commonStyles, colors } from '../styles/commonStyles';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import Icon from '../components/Icon';
import { mockCards, CardSummary } from '../data/mockCards';

type SortOption =
  | 'relevance'
  | 'price-desc'
  | 'price-asc'
  | 'name-asc'
  | 'name-desc'
  | 'number-asc'
  | 'number-desc';

export default function SearchScreen() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFilter, setSelectedFilter] = useState('all');
  const [sortOption, setSortOption] = useState<SortOption>('relevance');

  const filters = [
    { id: 'all', name: 'All Cards' },
    { id: 'rare', name: 'Rare' },
    { id: 'ultra', name: 'Ultra Rare' },
    { id: 'secret', name: 'Secret Rare' },
  ];

  const sortOptions: { id: SortOption; name: string }[] = [
    { id: 'relevance', name: 'Najtrafniejsze' },
    { id: 'price-desc', name: 'Cena malejąco' },
    { id: 'price-asc', name: 'Cena rosnąco' },
    { id: 'name-asc', name: 'Nazwa A-Z' },
    { id: 'name-desc', name: 'Nazwa Z-A' },
    { id: 'number-asc', name: 'Numer rosnąco' },
    { id: 'number-desc', name: 'Numer malejąco' },
  ];

  const filteredCards = useMemo(() => {
    const loweredQuery = searchQuery.trim().toLowerCase();

    return mockCards.filter((card) => {
      const matchesSearch =
        loweredQuery.length === 0 ||
        card.name.toLowerCase().includes(loweredQuery) ||
        card.set.toLowerCase().includes(loweredQuery) ||
        card.number.toLowerCase().includes(loweredQuery);

      const matchesFilter =
        selectedFilter === 'all' ||
        (selectedFilter === 'rare' && card.rarity.includes('Rare')) ||
        (selectedFilter === 'ultra' && card.rarity.includes('Ultra')) ||
        (selectedFilter === 'secret' && card.rarity.includes('Secret'));

      return matchesSearch && matchesFilter;
    });
  }, [searchQuery, selectedFilter]);

  const sortedCards = useMemo(() => {
    const cards = [...filteredCards];

    switch (sortOption) {
      case 'price-desc':
        return cards.sort((a, b) => b.price - a.price);
      case 'price-asc':
        return cards.sort((a, b) => a.price - b.price);
      case 'name-asc':
        return cards.sort((a, b) => a.name.localeCompare(b.name));
      case 'name-desc':
        return cards.sort((a, b) => b.name.localeCompare(a.name));
      case 'number-asc':
        return cards.sort((a, b) => a.number.localeCompare(b.number));
      case 'number-desc':
        return cards.sort((a, b) => b.number.localeCompare(a.number));
      default:
        return cards;
    }
  }, [filteredCards, sortOption]);

  const renderCard = ({ item }: { item: CardSummary }) => (
    <TouchableOpacity
      style={styles.cardTile}
      activeOpacity={0.9}
      onPress={() => router.push(`/card/${item.id}`)}
    >
      <View style={styles.cardImageWrapper}>
        <Image source={{ uri: item.image }} style={styles.cardImage} resizeMode="cover" />
        <Pressable
          style={styles.addButton}
          onPress={(event) => {
            event.stopPropagation();
            console.log('Add to collection:', item.name);
          }}
          hitSlop={12}
        >
          <Icon name="add" size={18} color={colors.primary} />
        </Pressable>
      </View>
      <View style={styles.cardInfo}>
        <Text style={styles.cardTitle} numberOfLines={2}>
          {item.name}
        </Text>
        <Text style={styles.cardMeta} numberOfLines={1}>
          #{item.number} · {item.set}
        </Text>
        <Text style={styles.cardRarity}>{item.rarity}</Text>
        <Text style={styles.cardPrice}>${item.price}</Text>
      </View>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={commonStyles.container}>
      {/* Header */}
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          paddingHorizontal: 20,
          paddingVertical: 16,
          backgroundColor: colors.backgroundAlt,
          borderBottomWidth: 1,
          borderBottomColor: colors.grey,
        }}
      >
        <TouchableOpacity onPress={() => router.back()}>
          <Icon name="arrow-back" size={24} color={colors.text} />
        </TouchableOpacity>
        <Text style={[commonStyles.subtitle, { marginLeft: 16, margin: 0 }]}>Search Cards</Text>
      </View>

      <View style={{ flex: 1 }}>
        {/* Search Input */}
        <View style={commonStyles.section}>
          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              backgroundColor: colors.backgroundAlt,
              borderRadius: 8,
              paddingHorizontal: 16,
              borderWidth: 1,
              borderColor: colors.grey,
            }}
          >
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

        {/* Filters & Sorting */}
        <View style={[commonStyles.section, { marginBottom: 16 }]}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingRight: 20 }}>
            {filters.map((filter) => (
              <TouchableOpacity
                key={filter.id}
                style={[
                  styles.chip,
                  {
                    backgroundColor: selectedFilter === filter.id ? colors.primary : colors.backgroundAlt,
                    borderColor: selectedFilter === filter.id ? colors.primary : colors.grey,
                  },
                ]}
                onPress={() => setSelectedFilter(filter.id)}
              >
                <Text
                  style={{
                    color: selectedFilter === filter.id ? colors.backgroundAlt : colors.text,
                    fontWeight: '500',
                  }}
                >
                  {filter.name}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
          <View style={{ marginTop: 16 }}>
            <View style={styles.sortHeader}>
              <Icon name="swap-vertical" size={16} color={colors.textLight} />
              <Text style={[commonStyles.textLight, { marginLeft: 6 }]}>Sortuj wyniki</Text>
            </View>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={{ paddingRight: 20, marginTop: 12 }}
            >
              {sortOptions.map((option) => (
                <TouchableOpacity
                  key={option.id}
                  style={[
                    styles.chip,
                    {
                      backgroundColor: sortOption === option.id ? colors.secondary : colors.backgroundAlt,
                      borderColor: sortOption === option.id ? colors.secondary : colors.grey,
                    },
                  ]}
                  onPress={() => setSortOption(option.id)}
                >
                  <Text
                    style={{
                      color: sortOption === option.id ? colors.primary : colors.text,
                      fontWeight: '500',
                    }}
                  >
                    {option.name}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        </View>

        {/* Results */}
        <View style={{ flex: 1 }}>
          <View style={{ paddingHorizontal: 20 }}>
            <Text style={[commonStyles.textLight, { marginBottom: 12 }]}>{sortedCards.length} cards found</Text>
          </View>

          <FlatList
            data={sortedCards}
            renderItem={renderCard}
            keyExtractor={(item) => item.id.toString()}
            numColumns={2}
            columnWrapperStyle={{ justifyContent: 'space-between' }}
            showsVerticalScrollIndicator={false}
            contentContainerStyle={{ paddingBottom: 120, paddingHorizontal: 14 }}
          />
        </View>
      </View>

      {/* Bottom Navigation */}
      <View
        style={{
          flexDirection: 'row',
          backgroundColor: colors.backgroundAlt,
          borderTopWidth: 1,
          borderTopColor: colors.grey,
          paddingVertical: 12,
        }}
      >
        <TouchableOpacity style={{ flex: 1, alignItems: 'center', paddingVertical: 8 }} onPress={() => router.push('/home')}>
          <Icon name="home" size={24} color={colors.text} />
          <Text style={[commonStyles.textLight, { fontSize: 12, marginTop: 4 }]}>Home</Text>
        </TouchableOpacity>
        <TouchableOpacity style={{ flex: 1, alignItems: 'center', paddingVertical: 8 }} onPress={() => router.push('/search')}>
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
        <TouchableOpacity style={{ flex: 1, alignItems: 'center', paddingVertical: 8 }} onPress={() => router.push('/profile')}>
          <Icon name="person" size={24} color={colors.text} />
          <Text style={[commonStyles.textLight, { fontSize: 12, marginTop: 4 }]}>Profile</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  cardTile: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 12,
    marginBottom: 16,
    flex: 1,
    marginHorizontal: 6,
    shadowColor: '#000000',
    shadowOpacity: 0.08,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  },
  cardImageWrapper: {
    borderRadius: 14,
    overflow: 'hidden',
    backgroundColor: colors.background,
  },
  cardImage: {
    width: '100%',
    aspectRatio: 63 / 88,
  },
  addButton: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.secondary,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000000',
    shadowOpacity: 0.15,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  cardInfo: {
    marginTop: 12,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.text,
  },
  cardMeta: {
    fontSize: 13,
    color: colors.textLight,
    marginTop: 6,
  },
  cardRarity: {
    fontSize: 12,
    color: colors.textLight,
    marginTop: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  cardPrice: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.primary,
    marginTop: 10,
  },
  chip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    marginRight: 12,
    borderWidth: 1,
  },
  sortHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
});
