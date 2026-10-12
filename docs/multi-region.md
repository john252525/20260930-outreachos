# Multi-region groundwork

> Документ описывает **подготовку** к multi-region. Реализация — Спринт 8.
> Сейчас всё работает в одном регионе (один VPS, docker-compose).

## Зачем multi-region

1. **Data residency** — клиенты из EU требуют хранения данных в EU (GDPR).
2. **Deliverability** — отправка из «местного» региона повышает доверие почтовых провайдеров.
3. **Failover** — падение одного региона не должно останавливать весь сервис.
4. **Latency** — приближение данных к пользователю.

## Модель данных: где что живёт

| Данные | Регион | Обоснование |
|---|---|---|
| `tenants`, `tenant_settings` | Global (replicated) | маршрутизация, конфиг |
| `briefs`, `icps`, `messages`, `replies` | Tenant home-region | персональные/бизнес-данные |
| `companies`, `contacts`, `stoplist_entries` | Tenant home-region | PII — residency |
| `sender_accounts`, `telegram/linkedin_accounts` | Tenant home-region | secrets, IP-привязка |
| `llm_calls`, `revisions`, `experiments` | Tenant home-region | производные бизнес-данных |
| NATS streams | per-region | локальная шина + мост |
| Redis | per-region | кэш, идемпотентность (не критичен для durability) |

**Принцип:** каждая сущность однозначно привязана к tenant; tenant имеет `home_region`.

## Стратегия репликации

- **Postgres** — logical replication (publication/subscription) для global-таблиц
  (`tenants`, `tenant_settings`) в глобальный «route» кластер. Бизнес-таблицы не реплицируются
  между регионами (остаются в home-region).
- **NATS** — JetStream per region; для глобальных событий — leaf nodes / gateways или
  `nats-server --cluster` с отдельным «route»-стримом.
- **Redis** — не реплицируем (кэш восстанавливается).
- **Объектное хранилище** (если появится) — S3 с cross-region replication.

## Роутинг

Вариант A (проще): **app-level**. BFF/API-gateway смотрит `tenant.home_region` и проксирует
запрос в нужный регион. Подходит, пока регионов мало (2-3).

Вариант B: **geo-DNS** (Route53 / Cloudflare) — `eu.api.example.com` → EU-кластер.
Требует разделения по пользователям/тенантам на DNS-уровне.

**Рекомендация:** начать с A (app-level), позже добавить B для публичных эндпоинтов.

## Миграция tenant между регионами (высокоуровнево)

1. Создать tenant-контейнер в целевом регионе (пустые таблицы).
2. `pg_dump`/logical-replication выбранных таблиц по `tenant_id`.
3. Синхронизировать NATS-консьюмеры (durable с фильтром по tenant).
4. Переключить `tenant.home_region` (глобальная таблица).
5. Drain и удалить данные в старом регионе (после верификации).

## Оценка стоимости

| Компонент | На регион |
|---|---|
| VPS (8 vCPU / 16 GB) | ~$40-80/мес |
| Managed Postgres | ~$50-150/мес |
| Object storage | по объёму |

MVP: 2 региона (eu + ru). Итого ~2× текущей инфры.

## План внедрения (Спринт 8)

1. Добавить `home_region` в `tenants` (глобальная таблица).
2. Разделить compose на per-region stack + global route-слой.
3. Настроить logical replication для global-таблиц.
4. Реализовать app-level роутинг в BFF.
5. Научить оркестратор работать в home-region tenant'а.
6. Failover-тесты.

## Не входит сейчас

- Реальная репликация, geo-DNS, автоматический failover.
- Разделение секретов по регионам (SOPS+age — отдельно).
