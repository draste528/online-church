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
### GET `/api/v1/items?category=candle&is_available=true`
Категории: `candle`, `icon`, `prosphora`, `incense`, `cross`, `literature`.
```json
// Response 200
[
  { "item_id": "a1c9...", "title": "Свеча восковая №10", "description": "Пчелиный воск",
    "category": "candle", "price": 15.00, "stock_quantity": 120, "image_url": "/img/candle10.jpg", "is_available": true }
]
```
### POST `/api/v1/items` (admin)
```json
{ "title": "Икона Спасителя", "category": "icon", "price": 450.00, "stock_quantity": 10, "description": "", "image_url": null }
```
Также `PUT /api/v1/items/{item_id}` и `DELETE /api/v1/items/{item_id}` (admin).

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
Фонды: `general`, `temple_restoration`, `choir`, `charity`, `minecraft_church`. Валюта всегда `RUB`.

| Поле | Правило |
|---|---|
| `amount` | число больше 0, не больше 1 000 000, не более двух знаков после запятой |
| `target_fund` | один из фондов выше |
| `card_number` | 4 группы по 4 цифры; пробелы и дефисы допустимы |
| `card_expiry` | `ММ/ГГ`, не в прошлом (карта действует до конца указанного месяца) |
| `card_cvc` | ровно 3 цифры |

```json
// Request
{ "amount": 500.0, "target_fund": "minecraft_church", "card_number": "4111 1111 1111 1111", "card_expiry": "12/30", "card_cvc": "123" }
// Response 201
{ "donation_id": "9b7e...", "payment_status": "completed", "amount": 500.0, "currency": "RUB",
  "target_fund": "minecraft_church", "transaction_reference": "DON-20261015-4C343934121D",
  "card_last4": "1111", "minecraft_blocks_awarded": 500, "created_at": "2026-10-15T19:31:28Z", "demo": true }
```
`minecraft_blocks_awarded` равен целой части суммы для фонда `minecraft_church` (1 рубль = 1 блок) и `0` для остальных фондов. Ответ `422` — неверные поля, `503` — база данных недоступна. Запись создаётся в таблице `donations` со статусом `completed`.

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
### POST `/api/v1/chats/ai/messages` (Прихожанин)
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
Считается по таблице `donations` (только `payment_status = 'completed'` и `currency = 'RUB'`). Часы суток даны во временной зоне `ANALYTICS_TIMEZONE` (по умолчанию `Europe/Moscow`).
```json
{ "currency": "RUB", "total_amount": 19753.0, "donations_count": 26, "average_amount": 759.73,
  "by_fund": [ { "fund": "temple_restoration", "total": 8500.0, "count": 4, "share_percent": 43.0 } ],
  "by_hour": [ { "hour": 0, "count": 0, "total": 0.0 }, "... всего 24 элемента (0–23) ..." ],
  "peak_hour": 10, "timezone": "Europe/Moscow" }
```
Если пожертвований нет: нули, `by_fund: []`, `peak_hour: null`. `503` — нет связи с базой данных.

> Статус реализации: `/health`, пожертвования и аналитика реализованы; остальные эндпоинты проектируются и реализуются по задачам Sprint 2–3.
