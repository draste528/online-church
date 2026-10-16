# Online Church — Frontend

Клиентская часть сервиса «Онлайн-Церковь» (православный приход): каталог церковной лавки, подача записок, пожертвования, запись к священнику, ИИ-консультация, трансляции и аналитический дашборд.

## Описание проекта
Одностраничное приложение (SPA), которое обращается к REST API серверной части (порт 8080) и к аналитическому API (порт 8000). Тёмная православная тема с золотыми акцентами.

## Стек технологий
- TypeScript
- React 18
- Vite
- react-router-dom v6
- Axios
- Docker

## Запуск
```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

## Страницы
| Маршрут | Файл | Раздел API |
|---|---|---|
| `/` Главная (свеча онлайн) | `src/pages/HomePage.tsx` | — |
| `/shop` Лавка: поиск, сортировка, корзина, заказ | `src/pages/ShopPage.tsx` | `GET /api/v1/items`, `POST /api/v1/orders` |
| `/forgiveness` Прощение | `src/pages/ForgivenessPage.tsx` | — |
| `/library` Молитвы и Библия | `src/pages/LibraryPage.tsx` | — |
| `/donate` Пожертвования ($, демо-оплата картой, статистика) | `src/pages/DonatePage.tsx` | `POST /api/v1/donations`, `GET /api/v1/analytics/donations/summary` (порт 8000) |
| `/chat` ИИ-консультант | `src/pages/ChatPage.tsx` | `POST /api/v1/chats/messages` |

Маршрут `/donations` перенаправляет на `/donate`.

## Языки интерфейса (ru / en / be)
Все видимые тексты лежат в словарях `src/i18n/ru.ts` (основной), `en.ts`, `be.ts`; переключатель языка находится в шапке, выбор запоминается в `localStorage`. Словари `en` и `be` типизированы как `Messages` (тип словаря `ru`), поэтому сборка (`npm run build`) падает, если в каком-то языке пропущен или лишний ключ. В компонентах используется `const { m } = useI18n()`: не пишите текст прямо в JSX.

Не переводятся: названия и описания товаров лавки (данные каталога из БД) и тексты ошибок, которые присылает сам backend.

Чтобы добавить язык: создайте `src/i18n/xx.ts` с объектом типа `Messages`, зарегистрируйте его в `LOCALES` (`src/i18n/index.tsx`) и добавьте запись в `LANGUAGES` (`src/config.ts`).

## Ссылки
- Прототипы страниц (Figma): `<ссылка на Figma-проект>`
- Описание API сервера: [docs/API.md](../docs/API.md)
- Backend: [backend](../backend/README.md)

## Команда
Константин Ващеня (Team Lead), Соболевский Евгений (Backend), Цыро Тамара (Frontend), Нарель Антон (QA).
