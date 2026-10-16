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
};

export type Messages = typeof ru;
