# BACKLOG.md — TODO, техдолг, отложенное

> Чтобы агент не «чинил» то, что сознательно отложено, и видел известные ограничения.

## Осознанные ограничения (dev)

- **`SENDER_DRY_RUN=true`** на dev: sender-email НЕ отправляет реально, только логирует и пишет SendAttempt
  (`provider_message_id=dry-run-<id>`). Реальная отправка — явный флаг + подключённые ящики через API.
- **Нет внешних ключей OSINT** (Serper/Yandex/DaData/Hunter): в sourcing реально работает только
  `website_parser` (httpx+bs4). Остальные коннекторы регистрируются, если заданы ключи.
- **Playwright НЕ установлен** (импорт-guard): `website_parser` без JS-рендеринга. Если httpx вернул мало
  текста — fallback молча ничего не делает (`_render_with_playwright`).
- **`deepseek-flash` — reasoning-модель.** При малых `max_tokens` (например, 20) может вернуть пустой
  `content` (бюджет ушёл в reasoning). Для генеративных задач держать `max_tokens >= 512` (в composer — 2048, в icp — 16384).
- **Scorer (sourcing)** — эвристики, не LLM. Порог `SOURCING_MIN_SCORE` (по умолчанию 0.5).
- **Fuzzy-match компаний** — не делаем (только детерминированный дедуп в contact-store).

## Инфраструктурные нюансы

- **NATS JetStream лимиты:** `reserved_storage` = сумма `max_bytes` всех стримов, а не фактический объём.
  Пул `max_file_store: 8GB` (см. `infra/nats/nats-server.conf`, ADR-012). Перед новым стримом сверять сумму броней с пулом.
- **VPS «впритык»:** ~3.7 ГБ RAM, диск часто >80%. Сборка образов иногда таймаутит → помогает `docker builder prune -f`.
  Чужие контейнеры на сервере НЕ трогать. Redis при нехватке памяти иногда даёт `Timeout connecting to server`
  в IdempotencyMiddleware (транзиентно).
- **Stage/prod** ещё не заведены (только dev).

## Техдолг

- `IdempotencyMiddleware` пересобирает response body — для стриминговых ответов не сработает.
- `LLMRequest.raw` в провайдере не пишется в `llm_calls` (можно, если понадобится).
- `docs/contracts.md` слегка расходится с реализацией (напр. `BriefStatus += archived`), при желании синхронизировать.
- Нет автотестов на `fetcher.py` (требует сети).
- `llm-gateway`: события `llm.called`/`cost.recorded` зарезервированы в `Subjects`, но пока не публикуются
  (учёт идёт в таблицу `llm_calls`, cost-tracker — Спринт 5).

## Отложено (Next / Later)

- **Спринт 4:** `analytics-service` (метрики, reply rate, bounce rate, A/B), `reply-classifier` (классификация входящих), A/B-движок (Experiment first-class).
- **Спринт 5:** `cost-tracker`.
- **3D/3E:** Telegram/WhatsApp sender, LinkedIn.
- **2D:** зарубежные OSINT-источники (Crunchbase, LinkedIn).
- Stage/prod окружения, Prometheus+Grafana, Loki, backup Postgres, SOPS+age для секретов.
- IMAP-poller в sender-email: код не реализован в 3C (только dry-run отправка). Reply/bounce detection — позже.

## Идеи (не обязательства)

- `mock`-провайдер: расширить набор реалистичных ответов под будущие task_type.
- Мульти-канальность: email → telegram → whatsapp → linkedin.
- Ротация ящиков по нагрузке в sender-email (сейчас AccountSelector берёт первый подходящий).
