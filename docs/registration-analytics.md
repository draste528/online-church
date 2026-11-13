# Аналитика регистраций

Цель: понимать, кто регистрируется, откуда приходит и становится ли активным прихожанином. Данные считает сервис analytics (порт 8000) по таблицам `users` и `donations`.

## Что собираем

### Уже есть в БД

| Поле | Зачем |
|---|---|
| `created_at` | динамика регистраций, день недели и час |
| `role` | соотношение прихожан, священников и администраторов |
| `last_seen` | вернулся ли пользователь после регистрации |
| `is_deleted` | удалённые не учитываются |
| `donations.user_id` | активация: пожертвование после регистрации |

### Спрашиваем в форме регистрации (необязательно)

Поля есть в форме FE-005. Возраст и город сохраняются **только при согласии** `analytics_consent = true`.

| Поле | Значения | Зачем |
|---|---|---|
| `analytics_consent` | `true` / `false` | без согласия демография не хранится и не считается |
| `birth_year` | 1900 … текущий год − 14 | возрастные группы (14–17, 18–24, …, 65+) |
| `city` | до 80 символов | география прихожан |
| `acquisition_source` | `friends`, `search`, `social`, `parish`, `other` | «откуда вы о нас узнали» |
| `preferred_language` | `ru`, `en`, `be` | язык интерфейса |

### Собираем автоматически (без персональных данных)

| Поле | Как получить на фронте | Зачем |
|---|---|---|
| `utm_source`, `utm_medium`, `utm_campaign` | из параметров URL первого визита, хранить до регистрации в `sessionStorage` | какая реклама или пост приводят людей |
| `referrer_domain` | только домен из `document.referrer` (без пути и параметров) | с каких сайтов приходят |
| `device_type` | `mobile` / `tablet` / `desktop` по ширине экрана | для какой платформы важнее дизайн |

Не собираем: IP-адрес, точную геолокацию, полный User-Agent, полный адрес страницы-источника, пол, вероисповедание. Это персональные или особо чувствительные данные, без которых аналитика обходится.

## Правила приватности

1. Демография (возраст, город) учитывается только у пользователей с согласием.
2. **Порог анонимности** `min_group` (по умолчанию 5): категория, в которой меньше пяти человек, объединяется в `other`. Так нельзя вычислить конкретного человека («единственный пользователь 65+ из Гродно»).
3. Эндпоинт отдаёт только счётчики: ни имён, ни email, ни идентификаторов. Аналитика читает из `users` только перечисленные выше колонки.
4. Возраст хранится как год рождения, а не дата.

## Эндпоинт

`GET /api/v1/analytics/registrations/summary`

| Параметр | По умолчанию | Диапазон | Смысл |
|---|---|---|---|
| `days` | 30 | 1–365 | анализируемый период |
| `min_group` | 5 | 1–50 | порог анонимности |
| `top` | 10 | 1–50 | максимум категорий в разбивке, остальное — `other` |
| `activation_days` | 7 | 1–90 | пожертвование за столько дней после регистрации считается активацией |
| `return_hours` | 24 | 1–720 | `last_seen` позже регистрации на столько часов — пользователь вернулся |

```json
{ "total_users": 120, "new_users": 34, "previous_period_users": 20, "growth_percent": 70.0,
  "by_day": [ { "date": "2026-11-13", "registrations": 3 } ],
  "by_weekday": [ { "key": "mon", "count": 6, "share_percent": 17.6 } ],
  "by_hour": [ { "key": "0", "count": 0, "share_percent": 0.0 } ],
  "by_role": [ { "key": "parishioner", "count": 33, "share_percent": 97.1 } ],
  "consent_available": true, "consented_users": 21, "consent_rate_percent": 61.8,
  "by_source": [ { "key": "friends", "count": 14, "share_percent": 41.2 }, { "key": "other", "count": 4, "share_percent": 11.8 } ],
  "by_utm_source": [], "by_utm_campaign": [], "by_referrer": [], "by_device": [], "by_language": [],
  "by_age_group": [ { "key": "18-24", "count": 8, "share_percent": 38.1 } ],
  "top_cities": [ { "key": "Minsk", "count": 15, "share_percent": 71.4 } ],
  "activation": { "window_days": 7, "activated_users": 9, "activation_rate_percent": 26.5,
                  "avg_days_to_first_donation": 1.8, "return_window_hours": 24,
                  "returned_users": 17, "return_rate_percent": 50.0 },
  "available_fields": ["is_deleted", "last_seen", "analytics_consent", "birth_year", "city"],
  "min_group": 5, "timezone": "Europe/Moscow", "days": 30 }
```

- Разбивки описывают пользователей, зарегистрированных за последние `days` дней; `total_users` — все неудалённые.
- `available_fields` показывает, какие необязательные колонки уже есть в БД. Пока колонки нет, соответствующая разбивка пустая, ошибки нет.
- `by_age_group` и `top_cities` считаются только по согласившимся (`consented_users`).
- `503` — нет связи с БД или таблицы `users`, `422` — параметры вне диапазона.

Код: `analytics/src/api/routes/registrations.py`, тесты: `analytics/tests/test_registrations_summary.py`.

## Что нужно от команды

- **Backend (Евгений):** применить `analytics/sql/05_users_registration_profile.sql`, добавить поля в модель `User` и в `RegisterIn`. Сохранять `birth_year` и `city` только при `analytics_consent = true` (в БД это защищено ограничением `ck_users_demographics_consent`). `referrer_domain` обрезать до домена на сервере тоже.
- **Frontend (Тамара):** при первом визите сохранить `utm_*` и домен реферера в `sessionStorage`, определить `device_type` и передать всё это в `POST /auth/register`. Поля формы уже есть в FE-005.
- **Аналитика:** дашборд регистраций на странице статистики.
