# BACKLOG.md — TODO, техдолг, отложенное

> Чтобы агент не «чинил» то, что сознательно отложено.

## Известные ограничения (осознанные)

- `brief-service` в dev работает с `BRIEF_LLM_MODEL=mock` — реальные LLM-вызовы не проверены в dev.
- `llm-gateway` в dev: `DEFAULT_PROVIDER=mock` (проверка пайплайна без токенов).
- Langfuse — подключён кодом (опционально), но требует ключей в `.env`.
- `fetcher.py` не рендерит JS (только статический HTML).
- Тесты интеграционные (`-m integration`) требуют запущенного стека; в CI пока не гоняются.

## Известные нюансы
- **NATS JetStream лимиты:** `reserved_storage` = сумма `max_bytes` всех стримов, а не фактический объём.
  Сейчас пул `max_file_store: 8GB` (см. `infra/nats/nats-server.conf`, ADR-012), брони ~1.6 GiB.
  Перед добавлением нового стрима сверять сумму лимитов с пулом. Потолки стримов (256-512 MiB) на dev
  завышены — при желании можно ужать до 64-128 MiB, но фактических данных < 1 MiB, смысла мало.

## Отложено (Next / Later)

- Стандартизировать расчёт стоимости LLM: вынести цены в отдельный конфиг (сделано/в работе, см. reference/pricing.md).
- Stage и prod окружения (сейчас только dev).
- Prometheus + Grafana (метрики), Loki (логи) — Спринт 4+.
- `cost-tracker` сервис (учёт расходов по тенантам) — Спринт 5.
- Backup Postgres для stage/prod.
- SOPS + age для секретов stage/prod.
- `docs/contracts.md` синхронизировать с фактической реализацией (например, `BriefStatus += archived`).

## Известные нюансы
- `deepseek-flash` — **reasoning-модель**. При малых `max_tokens` (например, 20) может вернуть пустой `content` (весь бюджет ушёл в reasoning). Для генеративных задач держать `max_tokens >= 512`. Если нужен короткий ответ — не полагаться на малый лимит.

## Известные ограничения (dev-среда)
- **Память на VPS впритык** (~3.7 ГБ всего, часто <1 ГБ свободно). При нагрузке Redis иногда даёт
  `Timeout connecting to server` в IdempotencyMiddleware (транзиентно, ретрай проходит). Для stage/prod —
  больше RAM и/или отдельный Redis.
- **sourcing-service** без внешних ключей: доступен только `website_parser` (httpx+bs4). Serper/Yandex XML/
  DaData/Hunter регистрируются, если заданы ключи. Playwright НЕ установлен (импорт-guard): если httpx вернул
  мало текста — JS-рендеринга нет (см. `website_parser._render_with_playwright`).
- **Scorer**: компоненты `industry/size/geo/pain/trigger/role` — эвристики (не LLM). Порог `SOURCING_MIN_SCORE` (0.5).

## Техдолг

- `IdempotencyMiddleware` пересобирает response body — для стриминговых ответов не сработает (пока не критично).
- `LLMRequest.raw` в провайдере не используется в учёте (можно логировать в LlmCall при необходимости).
- В `replay` idempotency не сохраняется body для не-JSON ответов (сейчас ок).
- Нет автотестов на `fetcher.py` (требует сети).

## Идеи (не обязательства)

- `mock`-провайдер: расширить набор реалистичных ответов под будущие task_type.
- A/B-движок: поднимать эксперименты как first-class (Experiment-контракт уже есть).
- Мульти-канальность: email → telegram → whatsapp → linkedin.
