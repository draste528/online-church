# API «Онлайн-Церковь»

Формат обмена — JSON (`Content-Type: application/json`). Базовый адрес backend: `http://localhost:8080`, аналитики: `http://localhost:8000`. Авторизованные запросы содержат заголовок `Authorization: Bearer <JWT>`.

Единый формат ошибки:

```json
{ "detail": "Описание ошибки" }
```

Коды: `200 OK`, `201 Created`, `400/422` — ошибка валидации, `401` — нет токена или токен недействителен, `403` — нет прав, `404` — не найдено, `409` — уже существует, `429` — слишком много попыток, `503` — недоступна база данных.

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
Вход выдаёт два токена:
- **access-токен** (JWT, `expires_in` секунд, по умолчанию 60 минут) — в ответе; клиент держит его в памяти и шлёт в `Authorization: Bearer`;
- **refresh-токен** — в cookie `refresh_token` с флагами `HttpOnly; SameSite=Strict; Path=/api/v1/auth; Secure` (`Secure` отключается `COOKIE_SECURE=false`), живёт `REFRESH_EXPIRE_DAYS` (30 дней). JavaScript его не видит; браузер сам отправляет его на `/api/v1/auth/*`.

Запросы к `/auth/*` из браузера делаются с `credentials: 'include'`. Поэтому CORS работает с `Access-Control-Allow-Credentials: true` и списком конкретных адресов (`CORS_ORIGINS`, по умолчанию `http://localhost:3000`); `*` backend не принимает и не стартует.

### POST `/api/v1/auth/register` (Гость)
```json
// Request: обязательны username, email, password, остальное необязательно
{
  "username": "olga", "email": "olga@example.com", "password": "Str0ngPass1",
  "first_name": "Ольга", "last_name": "Иванова",
  "analytics_consent": true, "birth_year": 1990, "city": "Минск",
  "acquisition_source": "parish", "preferred_language": "ru",
  "utm_source": "vk", "utm_medium": "social", "utm_campaign": "easter",
  "referrer_domain": "https://www.example.com/news?id=1", "device_type": "mobile"
}
// Response 201 — тот же профиль, что /auth/me
{
  "user_id": "3f2b...", "username": "olga", "email": "olga@example.com",
  "first_name": "Ольга", "last_name": "Иванова", "role": "parishioner",
  "analytics_consent": true, "birth_year": 1990, "city": "Минск", "preferred_language": "ru"
}
```
- Роль всегда `parishioner` (поле `role` в запросе игнорируется). Email приводится к нижнему регистру; email и `username` уникальны без учёта регистра (в БД — уникальный индекс на `lower(username)`), повтор — `409`.
- **Пароль**: от 10 символов, не длиннее 72 байт в UTF-8 (ограничение bcrypt; кириллица — 2 байта на символ), есть буква и цифра, не совпадает с email или `username` без учёта регистра. Иначе `422` с `loc: ["body", "password"]`.
- Поля профиля: `birth_year` — от 1900 до «текущий год − 14»; `city` — до 80 символов; `acquisition_source` — `friends | search | social | parish | other`; `preferred_language` — `ru | en | be`; `utm_source`, `utm_medium`, `utm_campaign` — до 100 символов; `device_type` — `mobile | tablet | desktop`. Неверное значение — `422` с `loc` этого поля. Пустая строка сохраняется как `null`.
- `birth_year` и `city` сохраняются только при `analytics_consent: true`, иначе записывается `null` (в БД — ограничение `ck_users_demographics_consent`).
- `referrer_domain` сервер обрезает до домена: без схемы, порта, пути и параметров, в нижнем регистре (`https://WWW.Example.com/a?b` → `www.example.com`); не похожее на домен значение сохраняется как `null`.
- UTM-метки, `referrer_domain`, `device_type` и `acquisition_source` нужны только аналитике и в профиле не возвращаются.

### POST `/api/v1/auth/login`
```json
// Request
{ "email": "olga@example.com", "password": "Str0ngPass1" }
// Response 200 (+ Set-Cookie: refresh_token=...; HttpOnly; SameSite=Strict; Path=/api/v1/auth; Secure)
{ "access_token": "<JWT>", "token_type": "bearer", "expires_in": 3600, "role": "parishioner" }
```
- Неверный email или пароль — `401` с одинаковым текстом. После 5 неудачных попыток за 15 минут — `429` с заголовком `Retry-After` (секунды), даже для верного пароля.
- Роль проверяется по БД при каждом запросе, а не берётся из токена.

### POST `/api/v1/auth/refresh` (по cookie)
Тело не нужно. По cookie `refresh_token` возвращает новый access-токен в том же формате, что `/login`. Нет cookie, она отозвана, истекла или пользователь удалён — `401`. Так фронтенд восстанавливает вход после F5 и продлевает истёкший access-токен.

### POST `/api/v1/auth/logout` (по cookie)
Отзывает refresh-токен из cookie и удаляет cookie (`Max-Age=0`). Ответ `204` без тела, в том числе если cookie не было. Access-токен не нужен. Другие сессии пользователя (другие браузеры) не затрагиваются.

### GET `/api/v1/auth/me` (любая роль)
```json
{
  "user_id": "3f2b...", "username": "olga", "email": "olga@example.com",
  "first_name": "Ольга", "last_name": "Иванова", "role": "parishioner",
  "analytics_consent": true, "birth_year": 1990, "city": "Минск", "preferred_language": "ru"
}
```
### PATCH `/api/v1/auth/me` (любая роль)
```json
{ "first_name": "Ольга", "last_name": "Петрова", "analytics_consent": true, "city": "Гродно", "birth_year": 1985, "preferred_language": "en" }
```
Меняются только `first_name`, `last_name`, `city`, `birth_year`, `preferred_language`, `analytics_consent`; поля, которых нет в запросе, не меняются, остальные (`role`, `email`, `username`, ...) игнорируются. Если согласие отозвано (`analytics_consent: false`) или его нет, `birth_year` и `city` обнуляются. Ответ — профиль, как в `GET /me`.

### POST `/api/v1/auth/change-password` (любая роль)
```json
{ "current_password": "Str0ngPass1", "new_password": "N3wPassword!" }
```
Ответ `204`. Неверный текущий пароль — `422` с `loc: ["body", "current_password"]` (неудачи считаются вместе с неудачными входами, после 5 — `429`); новый пароль не по правилам — `422` с `loc: ["body", "new_password"]`. После смены все refresh-токены пользователя отзываются (другие браузеры выйдут при следующем обновлении токена), текущий браузер получает новую cookie. Уже выданные access-токены действуют до своего срока (до 60 минут).

### PATCH `/api/v1/users/{user_id}/role` (admin)
```json
{ "role": "priest" }
```
Роли: `parishioner`, `priest`, `admin`. Ответ — профиль пользователя, как в `/auth/me`. Свою роль изменить нельзя (`400`), неизвестный пользователь — `404`.

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
| GET | `/api/v1/analytics/orders/summary?days=14&top=5` | статистика заказов лавки (см. ниже) |
| GET | `/api/v1/analytics/registrations/summary?days=30&min_group=5` | кто регистрируется: динамика, каналы, устройства, возраст и город (с согласием), активация — см. [registration-analytics.md](registration-analytics.md) |
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

### GET `/api/v1/analytics/orders/summary`
Считается по таблицам `shop_orders` и `shop_order_lines`; история статусов `shop_order_events` (SCRUM-27) подключается автоматически, когда таблица появится. Параметры: `days` — длина ряда `by_day` (1–90, по умолчанию 14), `top` — сколько самых продаваемых товаров вернуть (1–20, по умолчанию 5). Дни считаются во временной зоне `ANALYTICS_TIMEZONE`.
```json
{ "currency": "USD", "orders_count": 4, "active_orders": 2, "completed_orders": 1, "cancelled_orders": 1,
  "cancellation_rate_percent": 25.0, "revenue": 31.0, "average_order_value": 10.33, "items_sold": 8,
  "by_status": [ { "status": "accepted", "count": 1, "share_percent": 25.0 }, "... все 5 статусов ..." ],
  "funnel": [ { "status": "accepted", "reached": 4, "reached_percent": 100.0 }, "... assembling, ready, completed ..." ],
  "top_items": [ { "title": "Свеча", "quantity": 6, "revenue": 18.0 } ],
  "by_day": [ { "date": "2026-11-06", "orders": 1, "revenue": 18.5 } ],
  "fulfilment": { "tracking_available": true, "avg_hours_to_ready": 3.0, "avg_hours_to_completed": 6.0 },
  "timezone": "Europe/Moscow", "days": 14 }
```
Отменённые заказы входят в счётчики и `cancellation_rate_percent`, но не в выручку, `top_items` и `by_day.revenue`. `funnel` — сколько заказов дошло до шага (дошедший до `ready` учитывается и в `assembling`): с историей статусов — по событиям, без неё — по текущему статусу. Пока таблицы истории нет: `fulfilment.tracking_available = false`, времена `null`. `422` — `days`/`top` вне диапазона, `503` — нет связи с базой данных или таблиц лавки.

> Статус реализации: `/health`, лавка и заказы, пожертвования, чат и аналитика реализованы; остальные эндпоинты проектируются и реализуются по задачам Sprint 2–3.
