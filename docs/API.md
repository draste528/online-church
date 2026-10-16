# API «Онлайн-Церковь»

Формат обмена — JSON (`Content-Type: application/json`). Базовый адрес backend: `http://localhost:8080`, аналитики: `http://localhost:8000`. Авторизованные запросы содержат заголовок `Authorization: Bearer <JWT>`.

Единый формат ошибки:

```json
{ "detail": "Описание ошибки" }
```

Коды: `200 OK`, `201 Created`, `400/422` — ошибка валидации, `401` — нет токена, `403` — нет прав, `404` — не найдено, `503` — недоступна база данных.

Ошибка валидации `422` содержит список полей (значения, которые прислал клиент, в ответ не возвращаются):

```json
{ "detail": [ { "loc": ["body", "card_number"], "msg": "Номер карты: 16 цифр в четыре группы по четыре (пробелы и дефисы допустимы).", "type": "value_error" } ] }
```

Каждый ответ backend и analytics содержит заголовок `X-Request-ID` (8 символов): тот же идентификатор стоит в строках лога этого запроса.

## Система
| Метод | Путь | Описание |
|---|---|---|
| GET | `/health` | `{"status": "ok", "service": "online-church-backend"}` |

## Авторизация
### POST `/api/v1/auth/register` (Гость)
```json
// Request
{ "username": "olga", "email": "olga@example.com", "password": "Str0ngPass!", "first_name": "Ольга", "last_name": "Иванова" }
// Response 201
{ "user_id": "3f2b...", "username": "olga", "role": "parishioner" }
```
### POST `/api/v1/auth/login`
```json
// Request
{ "email": "olga@example.com", "password": "Str0ngPass!" }
// Response 200
{ "access_token": "<JWT>", "token_type": "bearer", "role": "parishioner" }
```

## Церковная лавка (экран «Лавка»)
Каталог и заказы хранятся в БД (таблицы `items`, `shop_orders`, `shop_order_lines`). Пустой каталог при старте backend заполняется демо-товарами (`SEED_ON_STARTUP=false` отключает). Если БД недоступна, эндпоинты отвечают `503`.

### GET `/api/v1/items`
Все параметры необязательные: `category`, `is_available`, `q` (поиск без учёта регистра по названию и описанию, в том числе по кириллице), `min_price`, `max_price`, `sort` (`default`, `price_asc`, `price_desc`, `title`).
Категории: `candle`, `icon`, `prosphora`, `incense`, `cross`, `literature`.
```json
// GET /api/v1/items?category=candle&is_available=true&sort=price_asc
[
  { "item_id": "7c1b8a52-0c3e-4a6e-9a47-3d4a1f9c2b10", "title": "Свеча восковая церковная", "description": "Натуральный воск, для домашней молитвы.",
    "category": "candle", "price": 1.5, "stock_quantity": 200, "image_url": null, "is_available": true }
]
```
### GET `/api/v1/items/categories`
Категории, в которых есть товары, со счётчиком: `[{ "category": "candle", "count": 3 }]`.
### GET `/api/v1/items/{item_id}`
Один товар (`item_id` — UUID); `404`, если товара нет, `422`, если идентификатор не UUID.
### POST `/api/v1/orders`
Оформление корзины. Проверка остатков, сохранение заказа и списание остатков выполняются в одной транзакции; повторяющиеся строки суммируются; когда остаток доходит до нуля, товар становится недоступным (`is_available = false`).
```json
// Request: 1..50 строк, quantity 1..99, customer_name необязательно (до 80 символов)
{ "lines": [ { "item_id": "7c1b8a52-0c3e-4a6e-9a47-3d4a1f9c2b10", "quantity": 2 } ], "customer_name": "Ольга" }
// Response 201
{ "order_id": "5e0f...", "status": "accepted", "total": 3.0,
  "lines": [ { "item_id": "7c1b...", "title": "Свеча восковая церковная", "quantity": 2, "unit_price": 1.5, "line_total": 3.0 } ] }
```
Ответы: `404` — товара нет, `409` — товар недоступен или не хватает остатка (заказ не сохраняется и остатки не меняются), `422` — неверный запрос.

### Запросы администратора (проектируются)
`POST /api/v1/items`, `PUT /api/v1/items/{item_id}` и `DELETE /api/v1/items/{item_id}` (admin) пока не реализованы.

## Записки (экран «Требы»)
### POST `/api/v1/treby` (Прихожанин)
Типы: `health`, `repose`, `sorokoust`, `moleben`, `blessing`. От 1 до 15 имён.
```json
// Request
{ "treba_type": "health", "commemoration_names": ["Алексий", "Ольга", "болящ. Сергий"], "donation_amount": 200.0 }
// Response 201
{ "status": "success", "order_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "message": "Записка принята к поминовению на Литургии", "minecraft_blocks_awarded": 200 }
```
### GET `/api/v1/treby/my`
Список записок пользователя: `[{ "order_id": "...", "treba_type": "health", "commemoration_names": [...], "status": "submitted", "created_at": "..." }]`

### PATCH `/api/v1/treby/{order_id}` (priest)
```json
{ "status": "completed" }
```
Статусы: `submitted`, `accepted`, `completed`, `cancelled`.

## Пожертвования
> **Оплата демонстрационная.** Деньги не списываются: если формат данных карты верен, платёж считается успешным. Номер карты и CVC не сохраняются и не пишутся в лог, в ответе возвращаются только последние 4 цифры.

### POST `/api/v1/donations`
Фонды: `general`, `temple_restoration`, `choir`, `charity`, `minecraft_church`. Валюта всегда `USD` (доллары США).

| Поле | Правило |
|---|---|
| `amount` | число больше 0, не больше 5 000, не более двух знаков после запятой (форма на сайте принимает от 1 до 5 000) |
| `target_fund` | один из фондов выше |
| `card_number` | 4 группы по 4 цифры; пробелы и дефисы допустимы |
| `card_expiry` | `ММ/ГГ`, не в прошлом (карта действует до конца указанного месяца) |
| `card_cvc` | ровно 3 цифры |

```json
// Request
{ "amount": 25.0, "target_fund": "minecraft_church", "card_number": "4111 1111 1111 1111", "card_expiry": "12/30", "card_cvc": "123" }
// Response 201
{ "donation_id": "9b7e...", "payment_status": "completed", "amount": 25.0, "currency": "USD",
  "target_fund": "minecraft_church", "transaction_reference": "DON-20261015-4C343934121D",
  "card_last4": "1111", "minecraft_blocks_awarded": 25, "created_at": "2026-10-15T19:31:28Z", "demo": true }
```
`minecraft_blocks_awarded` равен целой части суммы для фонда `minecraft_church` (1 доллар = 1 блок) и `0` для остальных фондов. Ответ `422` — неверные поля, `503` — база данных недоступна. Запись создаётся в таблице `donations` со статусом `completed`.

## Запись к священнику
### GET `/api/v1/priests`
`[{ "user_id": "...", "first_name": "Иоанн", "last_name": "Петров" }]`
### GET `/api/v1/appointments/slots?priest_id=...&date=2026-10-05`
`[{ "scheduled_at": "2026-10-05T10:00:00+03:00", "is_free": true }]`
### POST `/api/v1/appointments` (Прихожанин)
Типы: `confession`, `pastoral_talk`, `baptism_counseling`.
```json
// Request
{ "priest_id": "...", "scheduled_at": "2026-10-05T10:00:00+03:00", "appointment_type": "pastoral_talk", "notes": "Беседа о посте" }
// Response 201
{ "appointment_id": "...", "status": "requested" }
```
### PATCH `/api/v1/appointments/{appointment_id}` (priest)
```json
{ "status": "approved" }
```
Статусы: `requested`, `approved`, `rejected`, `completed`.

## ИИ-консультант
### POST `/api/v1/chats/messages` (реализовано)
```json
// Request: content 1..2000 символов, history — до 20 предыдущих реплик (модели уходят последние 10)
{ "content": "Как правильно готовиться к исповеди?", "history": [ { "role": "user", "content": "Мир вам" }, { "role": "assistant", "content": "…" } ] }
// Response 200
{ "reply": "…текст ответа…", "disclaimer": "Разговор с ИИ-консультантом не заменяет таинство исповеди и личную беседу со священником.", "mode": "ai" }
```
`mode` — `ai` (ответ модели) или `demo` (ключ выбранного провайдера не задан). Ошибки сервиса ИИ приходят как `502`/`504` с понятным текстом в поле `detail` (всегда с кодом HTTP).

Провайдер выбирает переменная `CHAT_PROVIDER`: `openrouter` (по умолчанию, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_MAX_TOKENS`, `OPENROUTER_REASONING`) или `hive` (`HIVE_API_KEY`, `HIVE_MODEL`, `HIVE_BASE_URL`, `HIVE_TIMEOUT_SECONDS`, `HIVE_MAX_TOKENS`, `HIVE_REASONING_EFFORT`, `HIVE_TEMPERATURE`). В `OPENROUTER_MODEL` и `HIVE_MODEL` можно перечислить несколько моделей через запятую: при перегрузке или лимите запросов используется следующая. Формат ответа и тексты ошибок у обоих провайдеров одинаковые. Проверка связи с The Hive: `HIVE_API_KEY=... python -m backend.app.check_hive --chat "Как молиться?"`.

### POST `/api/v1/chats/ai/messages` (проект для авторизованных пользователей)
```json
// Request
{ "chat_id": null, "text_content": "Как правильно готовиться к исповеди?" }
// Response 200
{ "chat_id": "...", "reply": "…текст ответа…",
  "disclaimer": "Разговор с ИИ не заменяет таинство исповеди." }
```

## Аналитика (порт 8000)
| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/v1/analytics/summary?target_date=2026-09-20` | сборы по фондам за день (витрина `mart_daily_finances`) |
| GET | `/api/v1/analytics/funds-distribution` | распределение сборов по фондам |
| GET | `/api/v1/analytics/donations/summary` | статистика пожертвований (см. ниже) |
| GET | `/health` | проверка работоспособности |

### GET `/api/v1/analytics/donations/summary`
Считается по таблице `donations` (только `payment_status = 'completed'` и `currency = 'USD'`). Часы суток даны во временной зоне `ANALYTICS_TIMEZONE` (по умолчанию `Europe/Moscow`).
```json
{ "currency": "USD", "total_amount": 899.25, "donations_count": 24, "average_amount": 37.47,
  "by_fund": [ { "fund": "temple_restoration", "total": 400.0, "count": 4, "share_percent": 44.5 } ],
  "by_hour": [ { "hour": 0, "count": 0, "total": 0.0 }, "... всего 24 элемента (0–23) ..." ],
  "peak_hour": 10, "timezone": "Europe/Moscow" }
```
Строки с другой валютой (например, старые `RUB`) в статистику не попадают. Если пожертвований нет: нули, `by_fund: []`, `peak_hour: null`. `503` — нет связи с базой данных.

> Статус реализации: `/health`, лавка и заказы, пожертвования, чат и аналитика реализованы; остальные эндпоинты проектируются и реализуются по задачам Sprint 2–3.
