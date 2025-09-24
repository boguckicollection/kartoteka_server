export interface CardSummary {
  id: number;
  name: string;
  number: string;
  set: string;
  rarity: string;
  price: number;
  image: string;
}

export const mockCards: CardSummary[] = [
  {
    id: 1,
    name: 'Charizard VMAX',
    number: '074/073',
    set: "Champion's Path",
    price: 450,
    rarity: 'Secret Rare',
    image: 'https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=400&h=560&fit=crop',
  },
  {
    id: 2,
    name: 'Pikachu VMAX',
    number: '188/185',
    set: 'Vivid Voltage',
    price: 320,
    rarity: 'Rainbow Rare',
    image: 'https://images.unsplash.com/photo-1613771404721-1f92d799e49f?w=400&h=560&fit=crop',
  },
  {
    id: 3,
    name: 'Lugia VSTAR',
    number: '202/195',
    set: 'Silver Tempest',
    price: 280,
    rarity: 'Ultra Rare',
    image: 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=560&fit=crop',
  },
  {
    id: 4,
    name: 'Rayquaza VMAX',
    number: '218/203',
    set: 'Evolving Skies',
    price: 380,
    rarity: 'Secret Rare',
    image: 'https://images.unsplash.com/photo-1606107557195-0e29a4b5b4aa?w=400&h=560&fit=crop',
  },
  {
    id: 5,
    name: 'Mew VMAX',
    number: '269/264',
    set: 'Fusion Strike',
    price: 220,
    rarity: 'Ultra Rare',
    image: 'https://images.unsplash.com/photo-1613771404721-1f92d799e49f?w=400&h=560&fit=crop',
  },
  {
    id: 6,
    name: 'Arceus VSTAR',
    number: '123/172',
    set: 'Brilliant Stars',
    price: 180,
    rarity: 'Ultra Rare',
    image: 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=560&fit=crop',
  },
];
