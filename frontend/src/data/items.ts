export type Category = 'candle' | 'icon' | 'incense' | 'prosphora';

export interface ShopItem {
  id: string;
  title: string;
  category: Category;
  price: number;
  description: string;
  is_available: boolean;
}

export const CATEGORY_LABELS: Record<Category | 'all', string> = {
  all: 'Всё',
  candle: 'Свечи',
  icon: 'Иконы',
  incense: 'Ладан',
  prosphora: 'Просфоры',
};

/** Fallback catalogue used when the backend API is unreachable. */
export const FALLBACK_ITEMS: ShopItem[] = [
  { id: 'c1', title: 'Свеча восковая церковная', category: 'candle', price: 1.5, description: 'Натуральный воск, для домашней молитвы.', is_available: true },
  { id: 'c2', title: 'Свеча алтарная большая', category: 'candle', price: 6, description: 'Длительное горение, чистый воск.', is_available: true },
  { id: 'i1', title: 'Икона Спасителя', category: 'icon', price: 25, description: 'Освящённая икона на дереве.', is_available: true },
  { id: 'i2', title: 'Икона Божией Матери', category: 'icon', price: 28, description: 'Освящённая икона на дереве.', is_available: true },
  { id: 'a1', title: 'Афонский ладан', category: 'incense', price: 12, description: 'Благоухающий ладан с Афона, 50 г.', is_available: true },
  { id: 'p1', title: 'Просфора', category: 'prosphora', price: 2, description: 'Свежая просфора для поминовения.', is_available: true },
];
