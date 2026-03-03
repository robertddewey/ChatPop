import { giftApi } from './api';

export type GiftCategory = 'food' | 'fun' | 'love' | 'animals' | 'premium';

export interface GiftItem {
  id: string;
  emoji: string;
  name: string;
  price: number; // cents
  category: GiftCategory;
}

export interface GiftCategoryInfo {
  id: GiftCategory;
  label: string;
  emoji: string;
}

export const GIFT_CATEGORIES: GiftCategoryInfo[] = [
  { id: 'food', label: 'Food & Drink', emoji: '🍔' },
  { id: 'fun', label: 'Fun', emoji: '🎉' },
  { id: 'love', label: 'Love', emoji: '❤️' },
  { id: 'animals', label: 'Animals', emoji: '🐶' },
  { id: 'premium', label: 'Premium', emoji: '💎' },
];

// In-memory session cache for the gift catalog
let cachedGiftItems: GiftItem[] | null = null;
let cachedBulkActionThreshold: number = 2; // default fallback

// Hardcoded fallback items (used if API fetch fails)
const FALLBACK_GIFT_ITEMS: GiftItem[] = [
  { id: 'gift_coffee',    emoji: '☕', name: 'Coffee',     price: 100,   category: 'food' },
  { id: 'gift_donut',     emoji: '🍩', name: 'Donut',      price: 100,   category: 'food' },
  { id: 'gift_cookie',    emoji: '🍪', name: 'Cookie',     price: 200,   category: 'food' },
  { id: 'gift_icecream',  emoji: '🍦', name: 'Ice Cream',  price: 200,   category: 'food' },
  { id: 'gift_pizza',     emoji: '🍕', name: 'Pizza',      price: 300,   category: 'food' },
  { id: 'gift_taco',      emoji: '🌮', name: 'Taco',       price: 300,   category: 'food' },
  { id: 'gift_hamburger', emoji: '🍔', name: 'Hamburger',  price: 500,   category: 'food' },
  { id: 'gift_sushi',     emoji: '🍣', name: 'Sushi',      price: 500,   category: 'food' },
  { id: 'gift_cake',      emoji: '🎂', name: 'Cake',       price: 800,   category: 'food' },
  { id: 'gift_steak',     emoji: '🥩', name: 'Steak',      price: 1000,  category: 'food' },
  { id: 'gift_champagne', emoji: '🍾', name: 'Champagne',  price: 1500,  category: 'food' },
  { id: 'gift_lobster',   emoji: '🦞', name: 'Lobster',    price: 2500,  category: 'food' },
  { id: 'gift_balloon',   emoji: '🎈', name: 'Balloon',    price: 100,   category: 'fun' },
  { id: 'gift_party',     emoji: '🎉', name: 'Party',      price: 100,   category: 'fun' },
  { id: 'gift_dice',      emoji: '🎲', name: 'Dice',       price: 200,   category: 'fun' },
  { id: 'gift_game',      emoji: '🎮', name: 'Game',       price: 300,   category: 'fun' },
  { id: 'gift_guitar',    emoji: '🎸', name: 'Guitar',     price: 500,   category: 'fun' },
  { id: 'gift_fireworks', emoji: '🎆', name: 'Fireworks',  price: 500,   category: 'fun' },
  { id: 'gift_magic',     emoji: '🪄', name: 'Magic',      price: 800,   category: 'fun' },
  { id: 'gift_disco',     emoji: '🪩', name: 'Disco Ball', price: 1000,  category: 'fun' },
  { id: 'gift_ferris',    emoji: '🎡', name: 'Ferris Wheel', price: 1500, category: 'fun' },
  { id: 'gift_slot',      emoji: '🎰', name: 'Jackpot',    price: 2500,  category: 'fun' },
  { id: 'gift_flower',    emoji: '🌸', name: 'Flower',     price: 200,   category: 'love' },
  { id: 'gift_rose',      emoji: '🌹', name: 'Rose',       price: 300,   category: 'love' },
  { id: 'gift_chocolate', emoji: '🍫', name: 'Chocolate',  price: 500,   category: 'love' },
  { id: 'gift_teddy',     emoji: '🧸', name: 'Teddy Bear', price: 500,   category: 'love' },
  { id: 'gift_bouquet',   emoji: '💐', name: 'Bouquet',    price: 1000,  category: 'love' },
  { id: 'gift_lovebox',   emoji: '🎁', name: 'Gift Box',   price: 1000,  category: 'love' },
  { id: 'gift_heart',     emoji: '💖', name: 'Heart',      price: 1500,  category: 'love' },
  { id: 'gift_cupid',     emoji: '💘', name: 'Cupid',      price: 2000,  category: 'love' },
  { id: 'gift_lovelock',  emoji: '🔐', name: 'Love Lock',  price: 3000,  category: 'love' },
  { id: 'gift_ring',      emoji: '💍', name: 'Ring',       price: 5000,  category: 'love' },
  { id: 'gift_chick',     emoji: '🐥', name: 'Chick',      price: 100,   category: 'animals' },
  { id: 'gift_bunny',     emoji: '🐰', name: 'Bunny',      price: 200,   category: 'animals' },
  { id: 'gift_cat',       emoji: '🐱', name: 'Cat',        price: 300,   category: 'animals' },
  { id: 'gift_dog',       emoji: '🐶', name: 'Dog',        price: 300,   category: 'animals' },
  { id: 'gift_panda',     emoji: '🐼', name: 'Panda',      price: 500,   category: 'animals' },
  { id: 'gift_fox',       emoji: '🦊', name: 'Fox',        price: 500,   category: 'animals' },
  { id: 'gift_dolphin',   emoji: '🐬', name: 'Dolphin',    price: 800,   category: 'animals' },
  { id: 'gift_butterfly',  emoji: '🦋', name: 'Butterfly',  price: 800,   category: 'animals' },
  { id: 'gift_unicorn',   emoji: '🦄', name: 'Unicorn',    price: 1500,  category: 'animals' },
  { id: 'gift_dragon',    emoji: '🐉', name: 'Dragon',     price: 5000,  category: 'animals' },
  { id: 'gift_medal',     emoji: '🏅', name: 'Medal',      price: 1000,  category: 'premium' },
  { id: 'gift_trophy',    emoji: '🏆', name: 'Trophy',     price: 2500,  category: 'premium' },
  { id: 'gift_crown',     emoji: '👑', name: 'Crown',      price: 5000,  category: 'premium' },
  { id: 'gift_gem',       emoji: '💎', name: 'Diamond',    price: 10000, category: 'premium' },
  { id: 'gift_money',     emoji: '💰', name: 'Money Bag',  price: 15000, category: 'premium' },
  { id: 'gift_rocket',    emoji: '🚀', name: 'Rocket',     price: 25000, category: 'premium' },
  { id: 'gift_castle',    emoji: '🏰', name: 'Castle',     price: 35000, category: 'premium' },
  { id: 'gift_sportscar', emoji: '🏎️', name: 'Sports Car', price: 50000, category: 'premium' },
];

export async function fetchGiftCatalog(code: string, roomUsername?: string): Promise<GiftItem[]> {
  // Return session cache if available
  if (cachedGiftItems) return cachedGiftItems;

  try {
    const response = await giftApi.getCatalog(code, roomUsername);
    cachedGiftItems = response.items.map(item => ({
      id: item.gift_id,
      emoji: item.emoji,
      name: item.name,
      price: item.price_cents,
      category: item.category as GiftCategory,
    }));
    if (response.bulk_action_threshold != null) {
      cachedBulkActionThreshold = response.bulk_action_threshold;
    }
    return cachedGiftItems;
  } catch (error) {
    console.error('[Gifts] Failed to fetch catalog, using fallback:', error);
    return FALLBACK_GIFT_ITEMS;
  }
}

export function getGiftItems(): GiftItem[] {
  return cachedGiftItems || FALLBACK_GIFT_ITEMS;
}

export function getGiftsByCategory(category: GiftCategory): GiftItem[] {
  const items = getGiftItems();
  return items.filter(g => g.category === category);
}

export function getGiftBulkActionThreshold(): number {
  return cachedBulkActionThreshold;
}

export function formatGiftPrice(cents: number): string {
  return `$${(cents / 100).toFixed(0)}`;
}
