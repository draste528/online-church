export const CATEGORIES = ['all', 'candle', 'icon', 'incense', 'prosphora', 'cross', 'literature'] as const;
export type CategoryFilter = (typeof CATEGORIES)[number];
export type Category = Exclude<CategoryFilter, 'all'>;

export interface ShopItem {
  id: string;
  title: string;
  category: Category;
  price: number;
  description: string;
  stock_quantity?: number;
  is_available: boolean;
}

/** Fallback catalogue used when the backend API is unreachable (orders cannot be placed with it). */
export const FALLBACK_ITEMS: ShopItem[] = [
  { id: 'c1', title: 'Свеча восковая церковная', category: 'candle', price: 1.5, description: 'Натуральный воск, для домашней молитвы.', is_available: true },
  { id: 'c2', title: 'Свеча алтарная большая', category: 'candle', price: 6, description: 'Длительное горение, чистый воск.', is_available: true },
  { id: 'i1', title: 'Икона Спасителя', category: 'icon', price: 25, description: 'Освящённая икона на дереве.', is_available: true },
  { id: 'i2', title: 'Икона Божией Матери', category: 'icon', price: 28, description: 'Освящённая икона на дереве.', is_available: true },
  { id: 'a1', title: 'Афонский ладан', category: 'incense', price: 12, description: 'Благоухающий ладан с Афона, 50 г.', is_available: true },
  { id: 'p1', title: 'Просфора', category: 'prosphora', price: 2, description: 'Свежая просфора для поминовения.', is_available: true },
  { id: 'x2', title: 'Нательный крестик, дерево', category: 'cross', price: 7, description: 'Резной кипарисовый крест.', is_available: true },
  { id: 'l1', title: 'Молитвослов', category: 'literature', price: 8, description: 'Утренние и вечерние молитвы, карманный формат.', is_available: true },
];
