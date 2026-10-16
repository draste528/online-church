/**
 * Russian texts: the source of truth for every other language.
 * `en.ts` and `be.ts` are typed as `Messages`, so the compiler reports a missing or extra key in any of them.
 */
export const ru = {
  meta: { title: 'Онлайн-Церковь | Православный приход' },
  brand: { title: 'Онлайн-Церковь', sub: 'Православный приход' },
  nav: {
    home: 'Главная',
    shop: 'Лавка',
    forgiveness: 'Прощение',
    library: 'Молитвы и Библия',
    donate: 'Пожертвования',
    chat: 'ИИ-консультант',
  },
  lang: { label: 'Язык' },
  footer: '© Онлайн-Церковь · Православный приход',
  shop: {
    title: 'Церковная лавка',
    categories: {
      all: 'Всё',
      candle: 'Свечи',
      icon: 'Иконы',
      incense: 'Ладан',
      prosphora: 'Просфоры',
      cross: 'Кресты',
      literature: 'Книги',
    },
    searchPlaceholder: 'Поиск по каталогу…',
    sortLabel: 'Сортировка',
    sort: { default: 'По умолчанию', price_asc: 'Сначала дешевле', price_desc: 'Сначала дороже', title: 'По названию' },
    offlineNote: 'Backend offline: показаны локальные данные (только в режиме разработки).',
    loading: 'Загрузка…',
    empty: 'Ничего не найдено.',
    addToCart: 'В корзину',
    cart: 'Корзина',
    cartEmpty: 'Пока пусто.',
    remove: 'Убрать',
    add: 'Добавить',
    total: 'Итого',
    checkout: 'Оформить заказ',
    checkingOut: 'Оформляем…',
    orderDone: 'Заказ принят',
    orderNumber: 'Номер заказа',
    orderError: 'Не удалось оформить заказ. Проверьте наличие и попробуйте ещё раз.',
  },
};

export type Messages = typeof ru;
