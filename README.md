# Online Church

Учебный веб-сервис онлайн-церкви: церковная лавка с заказами, прощение грехов, молитвы и Библия, пожертвования (в долларах США, демо-оплата картой, статистика), ИИ-консультант. Интерфейс на русском, английском и белорусском языках.

## Стек технологий
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Pydantic v2 (порт 8080)
- **Analytics:** Python, FastAPI, pandas (порт 8000)
- **Frontend:** TypeScript + React (Vite, порт 3000)
- **База данных:** PostgreSQL 16 (в docker compose); без Postgres backend использует локальный файл SQLite

## Команда проекта
- **Костя** — Team Lead (Архитектура, ревью, AI-интеграция)
- **Евгений** — Backend Developer (БД, EF Core, REST API)
- **Тамара** — Frontend Developer (UI, React-компоненты, API-интеграция)
- **Антон** — QA & Content (Seed-данные, документация, тестирование)

## Структура репозитория
- `/backend` — Исходный код API-сервера
- `/frontend` — Клиентская часть приложения
- `/docs` — Документация, Swagger-схемы, Postman-коллекции

## Запуск

### Всё сразу (docker compose)
```bash
docker compose up --build
```
| Сервис | Адрес |
|---|---|
| Frontend | http://localhost:3000 |
| Backend (Swagger: `/docs`) | http://localhost:8080 |
| Analytics (Swagger: `/docs`) | http://localhost:8000 |
| PostgreSQL | localhost:5432 (`church_admin` / `church_dwh`) |

Демо-пожертвования для статистики (`analytics/sql/03_seed_demo_donations.sql`) загружаются при **первом** старте пустой базы. Если том с базой уже существует, загрузите их вручную (команду можно запускать повторно, дубликатов не будет):
```bash
docker compose exec -T postgres_dwh psql -U church_admin -d church_dwh < analytics/sql/03_seed_demo_donations.sql
```

### Если база уже существует (пожертвования теперь в долларах)
Раньше пожертвования хранились с валютой `RUB`, теперь это `USD`: статистика и форма считают только `USD`, поэтому старые строки с `currency = 'RUB'` в статистику **не попадут**. Есть два варианта.

1. Начать с чистой базы (потеряются все данные, демо-пожертвования загрузятся заново в долларах):
```bash
docker compose down -v && docker compose up --build
```
2. Сохранить данные и пересчитать только метку валюты (суммы останутся прежними, это просто «доллары»):
```bash
docker compose exec -T postgres_dwh psql -U church_admin -d church_dwh -c "UPDATE donations SET currency='USD' WHERE currency='RUB';"
```
Таблицы лавки (`shop_orders`, `shop_order_lines`) backend создаёт сам при старте; в совсем новой базе их создаёт `docs/church_db_init.sql`. Если том с базой старый, а каталог `items` пуст, демо-товары добавятся автоматически.

### По отдельности (без docker)
```bash
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt -r analytics/requirements.txt
.venv/bin/uvicorn backend.app.main:app --port 8080          # без DATABASE_URL создаёт backend/church_dev.db (SQLite)
PYTHONPATH=. .venv/bin/uvicorn analytics.src.api.main:app --port 8000   # нужен PostgreSQL: docker compose up postgres_dwh, POSTGRES_HOST=localhost
cd frontend && npm install && npm run dev                    # http://localhost:3000
```

### Переменные окружения
Шаблоны: [.env.example](.env.example) (backend, analytics, docker compose) и [frontend/.env.example](frontend/.env.example). Реальные `.env` в git не попадают.

| Переменная | Где | По умолчанию | Назначение |
|---|---|---|---|
| `CHAT_PROVIDER` | backend | `openrouter` | какой ИИ-сервис отвечает в чате: `openrouter` или `hive` |
| `OPENROUTER_API_KEY` | backend | пусто | ключ ИИ-консультанта; без ключа выбранного провайдера чат работает в демо-режиме |
| `OPENROUTER_MODEL` | backend | `deepseek/deepseek-chat` | модель OpenRouter (можно несколько через запятую: следующая используется при перегрузке) |
| `HIVE_API_KEY` / `HIVE_MODEL` | backend | пусто / `deepseek-ai/deepseek-v4.1-flash` | The Hive (при `CHAT_PROVIDER=hive`); остальные `HIVE_*` см. в [.env.example](.env.example) |
| `SEED_ON_STARTUP` | backend | `true` | заполнить пустой каталог лавки демо-товарами при старте |
| `DATABASE_URL` | backend | локальный SQLite | строка подключения к БД (в compose — Postgres) |
| `LOG_LEVEL` | backend, analytics | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `CORS_ORIGINS` | backend, analytics | `*` | разрешённые адреса браузера через запятую |
| `POSTGRES_HOST` / `PORT` / `USER` / `PASSWORD` / `DB` | analytics | `postgres_dwh`, `5432`, … | подключение к БД |
| `ANALYTICS_TIMEZONE` | analytics | `Europe/Moscow` | часовой пояс для распределения пожертвований по часам |
| `VITE_API_URL` | frontend | `http://localhost:8080` | адрес backend (его открывает браузер, поэтому `localhost`, а не имя сервиса docker) |
| `VITE_ANALYTICS_URL` | frontend | `http://localhost:8000` | адрес analytics |

Переменные `VITE_*` читаются при старте dev-сервера: после изменения перезапустите `npm run dev`.

### Логи
```bash
docker compose logs -f backend_api analytics_api          # потоком
docker compose logs --tail 100 backend_api                # последние строки
LOG_LEVEL=DEBUG docker compose up -d backend_api          # подробнее (в том числе вызовы OpenRouter / The Hive)
```
Формат строки: `время уровень модуль [request-id] сообщение`. Каждый запрос пишет одну строку `GET /path -> 200 in 3.1 ms`, а ответ содержит заголовок `X-Request-ID` с тем же идентификатором, по нему легко найти все строки одного запроса. При старте backend и analytics печатают версию, режим чата, источник настроек и доступность БД. В логи никогда не попадают ключи ИИ-сервисов, номера карт, CVC и тексты сообщений пользователей (только их длина).

В режиме разработки (`npm run dev`) frontend пишет в консоль браузера `[api] ... failed`, а на странице лавки показывает пометку «Backend offline», если вместо данных API показаны локальные. Заказ при этом оформить нельзя: он идёт в API.

### Проверки (как в CI)
```bash
ruff check analytics/src analytics/tests backend/app backend/tests
PYTHONPATH=. pytest -v analytics/tests backend/tests
cd frontend && npm run build
```
