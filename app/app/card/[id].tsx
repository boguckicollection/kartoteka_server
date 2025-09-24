import React from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
import {
  ScrollView,
  View,
  Text,
  Image,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { commonStyles, colors } from '../../styles/commonStyles';
import Icon from '../../components/Icon';
import { mockCards } from '../../data/mockCards';

export default function CardDetailsScreen() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const card = mockCards.find((entry) => entry.id.toString() === id);

  return (
    <SafeAreaView style={commonStyles.container}>
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
        <Text style={[commonStyles.subtitle, { marginLeft: 16, margin: 0 }]}>Szczegóły karty</Text>
      </View>

      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 60 }}>
        {card ? (
          <>
            <View style={styles.heroWrapper}>
              <Image source={{ uri: card.image }} style={styles.heroImage} resizeMode="cover" />
            </View>

            <Text style={styles.cardName}>{card.name}</Text>
            <Text style={styles.cardMeta}>#{card.number} • {card.set}</Text>

            <View style={styles.tagRow}>
              <View style={styles.tagPill}>
                <Text style={styles.tagText}>{card.rarity}</Text>
              </View>
            </View>

            <View style={styles.priceCard}>
              <Text style={styles.sectionLabel}>Szacowana wartość</Text>
              <Text style={styles.priceValue}>${card.price}</Text>
              <TouchableOpacity
                style={styles.primaryAction}
                onPress={() => console.log('Add card to collection:', card.name)}
              >
                <Icon name="add" size={20} color={colors.primary} />
                <Text style={styles.primaryActionText}>Dodaj do kolekcji</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.infoCard}>
              <Text style={styles.sectionLabel}>Informacje o karcie</Text>
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Nazwa</Text>
                <Text style={styles.infoValue}>{card.name}</Text>
              </View>
              <View style={styles.divider} />
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Numer</Text>
                <Text style={styles.infoValue}>{card.number}</Text>
              </View>
              <View style={styles.divider} />
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Zestaw</Text>
                <Text style={styles.infoValue}>{card.set}</Text>
              </View>
              <View style={styles.divider} />
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Rzadkość</Text>
                <Text style={styles.infoValue}>{card.rarity}</Text>
              </View>
            </View>

            <View style={styles.descriptionCard}>
              <Text style={styles.sectionLabel}>Opis</Text>
              <Text style={styles.descriptionText}>
                Szczegółowe informacje o atakach, zdolnościach oraz historii wydania karty pojawią się tutaj,
                gdy tylko połączymy ekran z bazą danych. Na ten moment możesz podejrzeć podstawowe dane i dodać kartę do swojej
                kolekcji.
              </Text>
            </View>
          </>
        ) : (
          <View style={{ alignItems: 'center', marginTop: 60 }}>
            <Text style={[commonStyles.subtitle, { textAlign: 'center' }]}>Nie znaleziono karty</Text>
            <Text style={[commonStyles.textLight, { textAlign: 'center', marginTop: 8 }]}>
              Spróbuj wrócić do wyszukiwarki i wybrać inną kartę.
            </Text>
            <TouchableOpacity style={styles.primaryAction} onPress={() => router.back()}>
              <Icon name="arrow-back" size={20} color={colors.primary} />
              <Text style={styles.primaryActionText}>Wróć</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  heroWrapper: {
    borderRadius: 20,
    overflow: 'hidden',
    backgroundColor: colors.backgroundAlt,
    padding: 16,
    alignItems: 'center',
    shadowColor: '#000000',
    shadowOpacity: 0.08,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 4,
  },
  heroImage: {
    width: 260,
    aspectRatio: 63 / 88,
    borderRadius: 16,
  },
  cardName: {
    fontSize: 24,
    fontWeight: '700',
    color: colors.text,
    marginTop: 24,
  },
  cardMeta: {
    fontSize: 16,
    color: colors.textLight,
    marginTop: 8,
  },
  tagRow: {
    flexDirection: 'row',
    marginTop: 16,
  },
  tagPill: {
    backgroundColor: colors.secondary,
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
  },
  tagText: {
    color: colors.primary,
    fontWeight: '600',
    fontSize: 12,
    letterSpacing: 0.6,
  },
  priceCard: {
    marginTop: 28,
    backgroundColor: colors.backgroundAlt,
    borderRadius: 16,
    padding: 20,
    shadowColor: '#000000',
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
  sectionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textLight,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  priceValue: {
    fontSize: 28,
    fontWeight: '700',
    color: colors.primary,
    marginTop: 8,
  },
  primaryAction: {
    marginTop: 20,
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: colors.secondary,
    borderRadius: 999,
    paddingHorizontal: 18,
    paddingVertical: 10,
  },
  primaryActionText: {
    color: colors.primary,
    fontWeight: '600',
    fontSize: 14,
    marginLeft: 8,
  },
  infoCard: {
    marginTop: 28,
    backgroundColor: colors.backgroundAlt,
    borderRadius: 16,
    padding: 20,
    shadowColor: '#000000',
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
  },
  infoLabel: {
    fontSize: 14,
    color: colors.textLight,
  },
  infoValue: {
    fontSize: 16,
    color: colors.text,
    fontWeight: '600',
  },
  divider: {
    height: 1,
    backgroundColor: colors.grey,
    opacity: 0.5,
  },
  descriptionCard: {
    marginTop: 28,
    backgroundColor: colors.backgroundAlt,
    borderRadius: 16,
    padding: 20,
    shadowColor: '#000000',
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 2,
  },
  descriptionText: {
    fontSize: 14,
    color: colors.textLight,
    lineHeight: 22,
    marginTop: 12,
  },
});
