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
| Страница | Файл | Раздел API |
|---|---|---|
| Церковная лавка | `src/pages/CatalogPage.tsx` | `GET /api/v1/items` |
| Подача записок | `src/pages/TrebyPage.tsx` | `POST /api/v1/treby` |
| Консультация | `src/pages/ConfessionPage.tsx` | `/api/v1/chats/ai/messages`, `/api/v1/appointments` |
| Трансляции | `src/pages/StreamsPage.tsx` | — |
| Аналитика | `src/pages/AnalyticsDashboard.tsx` | `/api/v1/analytics/*` (порт 8000) |

## Ссылки
- Прототипы страниц (Figma): `<ссылка на Figma-проект>`
- Описание API сервера: [docs/API.md](../docs/API.md)
- Backend: [backend](../backend/README.md)

## Команда
Константин Ващеня (Team Lead), Соболевский Евгений (Backend), Цыро Тамара (Frontend), Нарель Антон (QA).
