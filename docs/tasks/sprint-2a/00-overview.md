# Спринт 2A — `contact-store`

Проверил: зависимости от Спринта 0 и 1 соблюдены, порядок задач логичен, acceptance criteria проверяемы, RLS корректен, дедуп детерминированный, нет противоречий с `docs/contracts.md`. Каждая задача самодостаточна.

## Что такое `contact-store` и почему он критичен

Это **единственный источник правды** по компаниям и контактам. Все остальные сервисы (sourcing, composer, reply-classifier, analytics) будут читать и писать сюда. Если модель данных кривая или дедуп плохой — мусор расползётся по всей платформе и его будет больно чистить.

**Ключевые принципы:**
1. **Дедуп детерминированный.** Никаких «похоже на то» на этом этапе. Только точные fingerprints.
2. **Upsert, не insert.** Sourcing будет совать одно и то же по десять раз — store должен мержить, не плодить дубликаты.
3. **Evidence сохраняется.** Каждое поле имеет `confidence` и `evidence`. Merge — по правилу «побеждает evidence с большей confidence».
4. **История аккумулируется.** `signals`, `outreach_history` — не перезаписываются, а дополняются.
5. **Stop-list проверяется до записи.** Если email в блок-листе — контакт не создаётся.

## Архитектура сервиса

```
                    ┌──────────────────────────────────────┐
                    │           contact-store              │
                    │                                       │
   HTTP requests ──►│  API layer (routes)                   │
                    │       │                               │
                    │       ▼                               │
                    │  CompanyService / ContactService      │
                    │       │                               │
                    │       ├──► Fingerprint (pure)         │
                    │       ├──► Merger (pure + DB)         │
                    │       ├──► StopList (DB)              │
                    │       └──► Repository (SQLAlchemy)    │
                    │                                       │
                    │  Events:                              │
                    │   - contact.created                   │
                    │   - contact.updated                   │
                    │   - contact.merged                    │
                    │   - contact.unsubscribed              │
                    │   - company.created                   │
                    │   - company.updated                   │
                    │   - company.merged                    │
                    └──────────────────────────────────────┘
                                      │
                                      ▼
                                   Postgres
```

**Что НЕ делает (осознанно):**
- Не ходит в интернет (это sourcing).
- Не вызывает LLM (кроме, может, fuzzy-match в будущем — но не в 2A).
- Не генерирует письма (это composer).
- Не считает метрики (это analytics).

**Модель данных:** Company и Contact — отдельные сущности в одной БД, в одном сервисе, но с разными таблицами. Связь: `Contact.company_id → Company.id` (nullable — бывают контакты без компании).

---

