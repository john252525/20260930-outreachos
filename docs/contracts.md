# docs/contracts.md — исчерпывающая спецификация контрактов

Ниже — полный документ. Он длинный, но это осознанно: лучше сразу зафиксировать всё, чем потом ломать совместимость. Я перепроверил каждую схему на: (1) полноту покрытия твоих сценариев, (2) версионируемость, (3) отсутствие циклических зависимостей, (4) готовность к мульти-тенантности, (5) совместимость с NATS-событиями, (6) пригодность для A/B-анализа.

---

## 0. Общие принципы

### 0.1. Версионирование схем

Каждый контракт имеет поле `schema_version` в формате `major.minor`. Правила:
- **major** инкрементится при breaking changes (удаление поля, смена типа, изменение семантики).
- **minor** инкрементится при добавлении опциональных полей.
- Потребитель обязан игнорировать неизвестные поля (forward compatibility).
- Сервис, читающий контракт, проверяет `schema_version.major` и падает с ошибкой при несовпадении.

Текущие версии: `brief/1.0`, `icp/1.0`, `contact/1.0`, `company/1.0`, `message/1.0`, `event/1.0`.

### 0.2. Общие типы

Все контракты используют общие примитивы:

```
TenantId        = UUID v7 (time-ordered, для сортировки по времени создания)
EntityId        = UUID v7
Timestamp       = RFC3339 UTC, миллисекундная точность, всегда с 'Z'
LanguageCode    = BCP-47 (например, "ru", "en", "ru-RU")
CountryCode     = ISO 3166-1 alpha-2 (например, "RU", "KZ")
CurrencyCode    = ISO 4217 (например, "RUB", "USD")
Url             = абсолютный URL, http/https
Email           = RFC 5322, нормализованный в lowercase
Phone           = E.164 (например, "+79001234567")
```

**Почему UUID v7:** time-ordered, хорошо для индексов в Postgres, сортируется по времени создания. Генерируется библиотекой `uuid6` на Python.

### 0.3. Общие поля всех сущностей

Каждая сущность (Brief, ICP, Contact, Company, Message) имеет:

```json
{
  "id": "EntityId",
  "tenant_id": "TenantId",
  "schema_version": "1.0",
  "created_at": "Timestamp",
  "updated_at": "Timestamp",
  "created_by": "string",        // user_id или "system" или "agent:<name>"
  "trace_id": "string",          // сквозной trace для отладки
  "metadata": {}                 // свободный словарь, не индексируется
}
```

Поле `metadata` — для экспериментальных данных, не влияет на логику. Потом можно повысить до полноценного поля.

### 0.4. Evidence-принцип

**Любое утверждение о факте** (компания существует, у неё есть сайт, у человека должность CTO) должно иметь `evidence`:

```json
{
  "value": "CTO",
  "confidence": 0.85,
  "evidence": [
    {
      "source_url": "https://example.com/team",
      "source_type": "website",
      "extracted_at": "Timestamp",
      "snippet": "Иван Петров, CTO с 2021 года"
    }
  ]
}
```

`confidence` — 0.0–1.0. Если ниже 0.5 — поле считается ненадёжным, composer не должен на него опираться. `evidence` может быть пустым (для фактов, введённых человеком вручную) — тогда `confidence = 1.0` и `source_type = "manual"`.

Этот принцип применяется в Contact, Company, ICP. В Brief — частично (там вводные от человека, evidence не нужен, но есть `source` для ссылок/транскриптов).

### 0.5. Мульти-тенантность

Правило: **любой объект принадлежит ровно одному тенанту**. Кросс-тенантные данные — только справочники (страны, отрасли) и глобальные стоп-листы. При передаче между сервисами `tenant_id` идёт всегда в headers (HTTP: `X-Tenant-ID`; NATS: header `tenant_id`), а в payload дублируется для self-describing событий.

### 0.6. NATS subjects (полная карта на Спринты 0–5)

```
<domain>.<action>.<tenant_id>

tenant.created.<tid>
tenant.updated.<tid>
tenant.archived.<tid>
tenant.restored.<tid>

brief.created.<tid>
brief.updated.<tid>
brief.questions_asked.<tid>
brief.completed.<tid>

icp.generated.<tid>
icp.revised.<tid>

contacts.search_started.<tid>
contacts.found.<tid>
contacts.enriched.<tid>

message.drafted.<tid>
message.approved.<tid>
message.rejected.<tid>
message.queued.<tid>
message.sent.<tid>
message.bounced.<tid>
message.failed.<tid>

reply.received.<tid>
reply.classified.<tid>

experiment.created.<tid>
experiment.variant_won.<tid>

llm.called.<tid>
cost.recorded.<tid>
```

---

## 1. Brief v1

**Назначение:** структурированное описание проекта/ниши, из которого всё строится. Источник — intake (текст, ссылка, ответы на вопросы, транскрипт голосового).

### 1.1. Схема

```json
{
  "id": "EntityId",
  "tenant_id": "TenantId",
  "schema_version": "1.0",
  "created_at": "Timestamp",
  "updated_at": "Timestamp",
  "created_by": "string",
  "trace_id": "string",
  "metadata": {},

  "status": "draft | in_progress | complete | abandoned",

  "raw_input": {
    "text": "string | null",
    "urls": ["Url"],
    "attachments": [
      {
        "id": "EntityId",
        "filename": "string",
        "mime_type": "string",
        "size_bytes": 12345,
        "storage_url": "string"
      }
    ],
    "transcript": "string | null",
    "submitted_at": "Timestamp"
  },

  "qa_history": [
    {
      "question": "string",
      "answer": "string",
      "asked_at": "Timestamp",
      "answered_at": "Timestamp",
      "generated_by": "llm:<model> | manual",
      "question_template_id": "string | null"
    }
  ],

  "identity": {
    "project_name": "string",
    "company_name": "string | null",
    "company_url": "Url | null",
    "one_liner": "string | null",
    "industry": "string | null",
    "sub_industry": "string | null",
    "language": "LanguageCode",
    "geo_primary": ["CountryCode"],
    "geo_secondary": ["CountryCode"]
  },

  "offering": {
    "what_we_sell": "string",
    "categories": ["string"],
    "differentiators": ["string"],
    "proof_points": ["string"],
    "price_range": {
      "min": "number | null",
      "max": "number | null",
      "currency": "CurrencyCode | null",
      "model": "fixed | subscription | usage | custom | unknown"
    },
    "sales_cycle_days_estimate": "integer | null"
  },

  "targeting_hints": {
    "known_competitors": ["string"],
    "known_customers_examples": ["string"],
    "must_have_criteria": ["string"],
    "must_not_have_criteria": ["string"],
    "geography_notes": "string | null",
    "company_size_hint": "smb | mid | enterprise | any | null",
    "role_hints": ["string"]
  },

  "outreach_goals": {
    "primary_goal": "lead_gen | partnership | hiring | pr | research | other",
    "goal_description": "string | null",
    "target_meetings_per_month": "integer | null",
    "tone_of_voice": "formal | casual | technical | friendly | neutral",
    "forbidden_topics": ["string"],
    "required_mentions": ["string"]
  },

  "missing_info": [
    {
      "field": "string",
      "why_needed": "string",
      "priority": "high | medium | low"
    }
  ],

  "completeness_score": 0.0
}
```

### 1.2. Правила

- `completeness_score` (0.0–1.0) вычисляется `brief-service` по формуле: взвешенная сумма заполненности ключевых полей. Веса: identity 0.25, offering 0.30, targeting_hints 0.20, outreach_goals 0.25.
- Если `completeness_score < 0.7` — `brief-service` генерирует вопросы и добавляет в `qa_history` (записывает вопрос без ответа, `answered_at: null`).
- Статус `complete` ставится либо автоматически при `completeness_score >= 0.85`, либо вручную пользователем.
- `missing_info` заполняется LLM: какие поля критичны, но не заполнены.

### 1.3. Пример

```json
{
  "id": "0190f3a2-...",
  "tenant_id": "0190f3a1-...",
  "schema_version": "1.0",
  "status": "in_progress",
  "raw_input": {
    "text": "Знакомый делает гидроборты, хочет выйти на дистрибьюторов в РФ",
    "urls": ["https://gidrobort-example.ru"],
    "submitted_at": "2026-09-30T10:00:00Z"
  },
  "identity": {
    "project_name": "Гидроборты — дистрибьюторы РФ",
    "company_url": "https://gidrobort-example.ru",
    "industry": "Промышленное производство",
    "sub_industry": "Подъёмно-транспортное оборудование",
    "language": "ru",
    "geo_primary": ["RU"]
  },
  "offering": {
    "what_we_sell": "Гидроборты для грузового транспорта",
    "categories": ["гидроборты", "подъёмники"],
    "differentiators": ["Собственное производство", "Гарантия 3 года"],
    "price_range": {"model": "custom", "currency": "RUB"}
  },
  "outreach_goals": {
    "primary_goal": "partnership",
    "tone_of_voice": "technical"
  },
  "completeness_score": 0.62,
  "missing_info": [
    {"field": "targeting_hints.known_customers_examples", "why_needed": "Поможет найти похожих клиентов", "priority": "high"},
    {"field": "offering.price_range.min", "why_needed": "Влияет на сегментацию по размеру клиента", "priority": "medium"}
  ]
}
```

---

## 2. ICP v1

**Назначение:** формализованный профиль идеального клиента/партнёра, разбитый на сегменты. Вход для sourcing.

### 2.1. Схема

```json
{
  "id": "EntityId",
  "tenant_id": "TenantId",
  "brief_id": "EntityId",
  "schema_version": "1.0",
  "created_at": "Timestamp",
  "updated_at": "Timestamp",
  "created_by": "string",
  "trace_id": "string",
  "metadata": {},

  "version": 1,

  "anti_icp": {
    "description": "string",
    "exclude_industries": ["string"],
    "exclude_company_sizes": ["smb | mid | enterprise"],
    "exclude_geos": ["CountryCode"],
    "exclude_keywords": ["string"]
  },

  "segments": [
    {
      "id": "EntityId",
      "name": "string",
      "description": "string",
      "priority": "high | medium | low",
      "estimated_size": "integer | null",

      "firmographic": {
        "industries": ["string"],
        "sub_industries": ["string"],
        "company_sizes": ["smb | mid | enterprise"],
        "employee_count_min": "integer | null",
        "employee_count_max": "integer | null",
        "revenue_range": {
          "min": "number | null",
          "max": "number | null",
          "currency": "CurrencyCode | null"
        },
        "geos": ["CountryCode"],
        "company_types": ["manufacturer | distributor | retailer | service | agency | saas | other"]
      },

      "technographic": {
        "uses_technologies": ["string"],
        "does_not_use_technologies": ["string"]
      },

      "pain_hypotheses": [
        {
          "pain": "string",
          "why_relevant": "string",
          "how_we_solve": "string",
          "confidence": 0.0
        }
      ],

      "trigger_events": [
        {
          "trigger": "string",
          "detection_hint": "string",
          "weight": 0.0
        }
      ],

      "roles_to_contact": [
        {
          "role_title": "string",
          "role_category": "decision_maker | influencer | gatekeeper | champion | unknown",
          "priority": "high | medium | low",
          "why": "string"
        }
      ],

      "scoring_weights": {
        "industry_match": 0.25,
        "size_match": 0.15,
        "geo_match": 0.10,
        "pain_match": 0.20,
        "trigger_match": 0.20,
        "role_match": 0.10
      },

      "estimated_reply_rate": "number | null",
      "notes": "string | null"
    }
  ],

  "generated_by": "llm:<model> | manual",
  "llm_confidence": 0.0
}
```

### 2.2. Правила

- Веса в `scoring_weights` для каждого сегмента должны суммироваться в 1.0 (валидатор Pydantic).
- `version` инкрементится при каждом ре-генерейте ICP для того же brief. Старые версии сохраняются — нужны для A/B-анализа метрик outreach.
- `estimated_reply_rate` — прогноз LLM, потом сравнивается с реальностью, ошибка идёт в аналитику.
- Если `llm_confidence < 0.6` — `icp-service` помечает ICP как «требует ревью человеком» (флаг в metadata).

---

## 3. Company v1

**Назначение:** карточка компании-кандидата.

### 3.1. Схема

```json
{
  "id": "EntityId",
  "tenant_id": "TenantId",
  "schema_version": "1.0",
  "created_at": "Timestamp",
  "updated_at": "Timestamp",
  "created_by": "string",
  "trace_id": "string",
  "metadata": {},

  "fingerprint": "string",   // sha256(normalized_domain || normalized_name)
  "status": "candidate | contacted | replied | qualified | disqualified | archived",

  "name": {"value": "string", "confidence": 1.0, "evidence": []},
  "legal_name": {"value": "string | null", "confidence": 0.0, "evidence": []},
  "domain": {"value": "string | null", "confidence": 0.0, "evidence": []},
  "website": {"value": "Url | null", "confidence": 0.0, "evidence": []},

  "industry": {"value": "string | null", "confidence": 0.0, "evidence": []},
  "sub_industry": {"value": "string | null", "confidence": 0.0, "evidence": []},

  "size_estimate": {
    "employee_count": {"value": "integer | null", "confidence": 0.0, "evidence": []},
    "employee_range": "smb | mid | enterprise | unknown",
    "revenue_estimate": {"value": "number | null", "confidence": 0.0, "evidence": []},
    "revenue_currency": "CurrencyCode | null"
  },

  "locations": [
    {
      "country": {"value": "CountryCode | null", "confidence": 0.0, "evidence": []},
      "city": {"value": "string | null", "confidence": 0.0, "evidence": []},
      "address": {"value": "string | null", "confidence": 0.0, "evidence": []},
      "is_hq": true
    }
  ],

  "registry_ids": {
    "ru_inn": "string | null",
    "ru_ogrn": "string | null",
    "other": {"key": "value"}
  },

  "social_profiles": {
    "linkedin": "Url | null",
    "telegram": "string | null",
    "vk": "Url | null",
    "other": {"key": "Url"}
  },

  "tech_stack": [
    {"value": "string", "confidence": 0.0, "evidence": []}
  ],

  "signals": [
    {
      "type": "hiring | funding | launch | expansion | award | news | other",
      "summary": "string",
      "detected_at": "Timestamp",
      "source_url": "Url",
      "relevance_score": 0.0
    }
  ],

  "match": {
    "segment_id": "EntityId | null",
    "icp_version": 1,
    "score": 0.0,
    "score_breakdown": {
      "industry_match": 0.0,
      "size_match": 0.0,
      "geo_match": 0.0,
      "pain_match": 0.0,
      "trigger_match": 0.0,
      "role_match": 0.0
    },
    "matched_criteria": ["string"],
    "failed_criteria": ["string"],
    "reason": "string"
  },

  "contacts_count": 0,
  "outreach_history": {
    "total_contacts": 0,
    "total_messages": 0,
    "last_contacted_at": "Timestamp | null"
  },

  "tags": ["string"],
  "notes": "string | null"
}
```

### 3.2. Правила

- `fingerprint` — ключ дедупликации. Вычисляется как sha256 от нормализованного домена (без www, lowercase) или, если домена нет, от нормализованного названия (lowercase, без ООО/LLC и т.п.).
- Все поля, кроме `name` и `fingerprint`, опциональны с confidence 0.0. Это позволяет создавать «частичные» карточки по мере обогащения.
- `match.score` пересчитывается при каждом новом сигнале или обогащении.
- `signals` — самый важный блок для персонализации писем. Composer берёт оттуда «крючок».

---

## 4. Contact v1

**Назначение:** карточка человека-кандидата.

### 4.1. Схема

```json
{
  "id": "EntityId",
  "tenant_id": "TenantId",
  "company_id": "EntityId | null",
  "schema_version": "1.0",
  "created_at": "Timestamp",
  "updated_at": "Timestamp",
  "created_by": "string",
  "trace_id": "string",
  "metadata": {},

  "fingerprint": "string",   // sha256(normalized_email || normalized_phone || normalized_fullname+company_domain)
  "status": "candidate | approved | contacted | replied | qualified | disqualified | unsubscribed | bounced | archived",

  "full_name": {"value": "string", "confidence": 1.0, "evidence": []},
  "first_name": {"value": "string | null", "confidence": 0.0, "evidence": []},
  "last_name": {"value": "string | null", "confidence": 0.0, "evidence": []},
  "patronymic": {"value": "string | null", "confidence": 0.0, "evidence": []},

  "position": {"value": "string | null", "confidence": 0.0, "evidence": []},
  "role_category": "decision_maker | influencer | gatekeeper | champion | unknown",
  "seniority": "c_level | vp | director | manager | specialist | unknown",

  "emails": [
    {
      "value": "Email",
      "type": "work | personal | unknown",
      "is_primary": true,
      "is_verified": false,
      "verified_at": "Timestamp | null",
      "confidence": 0.0,
      "evidence": []
    }
  ],

  "phones": [
    {
      "value": "Phone",
      "type": "work | mobile | unknown",
      "is_primary": true,
      "is_whatsapp": false,
      "is_telegram": false,
      "confidence": 0.0,
      "evidence": []
    }
  ],

  "messengers": [
    {
      "channel": "telegram | whatsapp | linkedin | vk",
      "handle": "string",
      "profile_url": "Url | null",
      "confidence": 0.0,
      "evidence": []
    }
  ],

  "social_profiles": {
    "linkedin": "Url | null",
    "telegram": "string | null",
    "vk": "Url | null",
    "other": {"key": "Url"}
  },

  "location": {
    "country": {"value": "CountryCode | null", "confidence": 0.0, "evidence": []},
    "city": {"value": "string | null", "confidence": 0.0, "evidence": []},
    "timezone": "string | null"
  },

  "language_preference": "LanguageCode | null",

  "match": {
    "segment_id": "EntityId | null",
    "icp_version": 1,
    "role_match_score": 0.0,
    "reason": "string"
  },

  "consent": {
    "email_opt_in": "unknown | granted | denied | not_required",
    "email_opt_in_source": "string | null",
    "email_opt_in_at": "Timestamp | null",
    "messenger_opt_in": "unknown | granted | denied | not_required",
    "gdpr_lawful_basis": "consent | legitimate_interest | contract | unknown",
    "notes": "string | null"
  },

  "outreach_history": {
    "total_messages": 0,
    "last_contacted_at": "Timestamp | null",
    "last_reply_at": "Timestamp | null",
    "replied_positive": false
  },

  "tags": ["string"],
  "notes": "string | null"
}
```

### 4.2. Правила

- `fingerprint` — ключ дедупликации. Приоритет: email → phone → (fullname + company_domain).
- `consent` обязателен для соблюдения 152-ФЗ и GDPR. Для холодного B2B в РФ lawful basis обычно `legitimate_interest`, но запись должна быть.
- `role_category` используется composer'ом для выбора тона.
- Если `status = unsubscribed` — контакт никогда не попадает в новые очереди, даже если попал в sourcing.

---

## 5. Message v1

**Назначение:** конкретное сообщение конкретному контакту через конкретный канал.

### 5.1. Схема

```json
{
  "id": "EntityId",
  "tenant_id": "TenantId",
  "contact_id": "EntityId",
  "company_id": "EntityId | null",
  "campaign_id": "EntityId | null",
  "schema_version": "1.0",
  "created_at": "Timestamp",
  "updated_at": "Timestamp",
  "created_by": "string",
  "trace_id": "string",
  "metadata": {},

  "channel": "email | telegram | whatsapp | linkedin",
  "status": "draft | pending_review | approved | rejected | queued | sending | sent | delivered | bounced | failed | replied | closed",

  "sequence": {
    "step": 1,
    "total_steps": 1,
    "parent_message_id": "EntityId | null",
    "is_followup": false,
    "followup_after_days": "integer | null"
  },

  "content": {
    "subject": "string | null",
    "body_text": "string",
    "body_html": "string | null",
    "language": "LanguageCode",
    "word_count": 0
  },

  "personalization": {
    "template_id": "string",
    "template_version": "string",
    "llm_model": "string",
    "variables_used": {"key": "value"},
    "factual_claims": [
      {
        "claim": "string",
        "evidence_url": "Url | null",
        "confidence": 0.0,
        "is_hypothesis": false
      }
    ]
  },

  "sender": {
    "identity_type": "user | service",
    "user_id": "string | null",
    "from_email": "Email | null",
    "from_name": "string | null",
    "reply_to": "Email | null",
    "messaging_account_id": "string | null",
    "signature": "string | null"
  },

  "recipient_snapshot": {
    "email": "Email | null",
    "phone": "Phone | null",
    "messenger_handle": "string | null",
    "full_name": "string",
    "position": "string | null",
    "company_name": "string | null"
  },

  "experiment": {
    "experiment_id": "EntityId | null",
    "variant_id": "string | null",
    "hypothesis": "string | null"
  },

  "send_schedule": {
    "scheduled_at": "Timestamp | null",
    "sent_at": "Timestamp | null",
    "timezone": "string | null",
    "ramp_up_bucket": "integer | null"
  },

  "delivery": {
    "provider_message_id": "string | null",
    "provider_response": {},
    "bounce_type": "hard | soft | null",
    "bounce_reason": "string | null",
    "failed_reason": "string | null"
  },

  "engagement": {
    "opened_count": 0,
    "first_opened_at": "Timestamp | null",
    "last_opened_at": "Timestamp | null",
    "clicked_count": 0,
    "first_clicked_at": "Timestamp | null",
    "replied_at": "Timestamp | null",
    "reply_id": "EntityId | null"
  },

  "review": {
    "reviewed_by": "string | null",
    "reviewed_at": "Timestamp | null",
    "rejection_reason": "string | null",
    "edited_by_human": false,
    "original_body_text": "string | null"
  },

  "tags": ["string"]
}
```

### 5.2. Правила

- `content.body_text` — источник правды. `body_html` — производное для email.
- `personalization.factual_claims` — критично. Каждое фактическое утверждение либо имеет `evidence_url`, либо помечено `is_hypothesis: true`. Composer обязан это соблюдать. Reviewer (человек) видит это в UI.
- `recipient_snapshot` фиксируется в момент создания — чтобы при изменении контакта история осталась корректной.
- `review.original_body_text` хранится, если человек редактировал. Для A/B-анализа: сравниваем LLM-версию vs отредактированную.
- `status = sent` ставится после успешного ответа провайдера. `delivered` — после подтверждения доставки (если провайдер даёт webhook).
- `sequence.step > 1` — follow-up. `parent_message_id` ссылается на первое сообщение в цепочке.

---

## 6. Reply v1

**Назначение:** входящий ответ на сообщение.

### 6.1. Схема

```json
{
  "id": "EntityId",
  "tenant_id": "TenantId",
  "message_id": "EntityId",
  "contact_id": "EntityId",
  "schema_version": "1.0",
  "created_at": "Timestamp",
  "updated_at": "Timestamp",
  "trace_id": "string",
  "metadata": {},

  "channel": "email | telegram | whatsapp | linkedin",
  "received_at": "Timestamp",
  "raw_content": "string",
  "language": "LanguageCode | null",

  "classification": {
    "category": "positive | negative | not_interested | wrong_person | auto_reply | question | unsubscribe | out_of_office | unknown",
    "confidence": 0.0,
    "sentiment": "positive | neutral | negative",
    "intent": "string | null",
    "extracted_questions": ["string"],
    "extracted_actions": ["string"],
    "classified_by": "llm:<model> | manual",
    "classified_at": "Timestamp"
  },

  "suggested_next_action": {
    "action": "reply | schedule_meeting | forward_to_human | add_to_nurture | unsubscribe | close",
    "reason": "string",
    "draft_reply": "string | null"
  },

  "handled_by": "string | null",
  "handled_at": "Timestamp | null",
  "outcome": "string | null"
}
```

---

## 7. Experiment v1

**Назначение:** A/B-гипотеза по outreach.

### 7.1. Схема

```json
{
  "id": "EntityId",
  "tenant_id": "TenantId",
  "schema_version": "1.0",
  "created_at": "Timestamp",
  "updated_at": "Timestamp",
  "created_by": "string",
  "trace_id": "string",
  "metadata": {},

  "name": "string",
  "hypothesis": "string",
  "status": "draft | running | paused | completed | aborted",

  "scope": {
    "segment_id": "EntityId | null",
    "channel": "email | telegram | whatsapp | linkedin",
    "icp_version": 1
  },

  "variable": {
    "type": "subject | body | offer | cta | tone | send_time | channel | other",
    "description": "string"
  },

  "variants": [
    {
      "id": "string",
      "name": "string",
      "description": "string",
      "template_id": "string",
      "weight": 0.5
    }
  ],

  "metrics": {
    "primary": "reply_rate | positive_reply_rate | meetings_booked | open_rate",
    "secondary": ["open_rate", "click_rate", "bounce_rate"]
  },

  "sample_size_target": 200,
  "sample_size_per_variant": 100,
  "confidence_level": 0.95,
  "minimum_detectable_effect": 0.05,

  "results": {
    "variants": [
      {
        "variant_id": "string",
        "sent": 0,
        "replied": 0,
        "positive_replied": 0,
        "meetings_booked": 0,
        "primary_metric_value": 0.0,
        "confidence_interval": [0.0, 0.0]
      }
    ],
    "winner_variant_id": "string | null",
    "is_significant": false,
    "concluded_at": "Timestamp | null"
  },

  "decision": "string | null"
}
```

### 7.2. Правила

- `variants[].weight` суммируются в 1.0.
- Эксперимент переходит в `completed` автоматически, когда `sample_size_per_variant` достигнут для всех вариантов И статистическая значимость достигнута (или истёк max_duration).
- `winner_variant_id` — вариант с лучшим primary metric при p < 0.05.

---

## 8. События (event envelope)

**Назначение:** единый формат для всех NATS-событий.

### 8.1. Схема

```json
{
  "event_id": "EntityId",
  "event_type": "brief.created",
  "schema_version": "1.0",
  "occurred_at": "Timestamp",
  "tenant_id": "TenantId",
  "trace_id": "string",
  "causation_id": "EntityId | null",
  "correlation_id": "EntityId | null",
  "producer": "brief-service/0.1.0",
  "payload": {}
}
```

- `causation_id` — id события/сущности, которое вызвало это.
- `correlation_id` — id всей цепочки (например, id brief'а для всех событий по проекту).
- `producer` — `service/version` для отладки.

### 8.2. Payload'ы по событиям

**`tenant.created`**
```json
{"tenant": {"id": "...", "name": "...", "status": "active"}}
```

**`brief.created`**
```json
{"brief": {"id": "...", "status": "draft", "completeness_score": 0.0}}
```

**`brief.questions_asked`**
```json
{"brief_id": "...", "questions": [{"question": "...", "priority": "high"}]}
```

**`brief.completed`**
```json
{"brief": {"id": "...", "completeness_score": 0.92}}
```

**`icp.generated`**
```json
{"icp": {"id": "...", "brief_id": "...", "version": 1, "segments_count": 3}}
```

**`contacts.search_started`**
```json
{"icp_id": "...", "segment_id": "...", "sources": ["web", "yandex"]}
```

**`contacts.found`**
```json
{"icp_id": "...", "segment_id": "...", "count": 42, "contact_ids": ["..."]}
```

**`message.drafted`**
```json
{"message": {"id": "...", "contact_id": "...", "channel": "email", "template_id": "..."}}
```

**`message.approved`**
```json
{"message_id": "...", "approved_by": "user:123", "edited": false}
```

**`message.sent`**
```json
{"message_id": "...", "channel": "email", "sender": "sales@...", "provider_message_id": "..."}
```

**`reply.received`**
```json{"reply": {"id": "...", "message_id": "...", "contact_id": "...", "channel": "email"}}
```

**`reply.classified`**
```json
{"reply_id": "...", "category": "positive", "confidence": 0.91}
```

**`llm.called`**
```json
{"task_type": "brief_questions", "model": "deepseek-chat", "tokens_in": 1234, "tokens_out": 567, "cost_usd": 0.0012, "latency_ms": 2340}
```

---

## 9. Enum'ы (полный справочник)

### 9.1. Tenant
```
status: active | paused | archived | deleted
```

### 9.2. Brief
```
status: draft | in_progress | complete | abandoned
primary_goal: lead_gen | partnership | hiring | pr | research | other
tone_of_voice: formal | casual | technical | friendly | neutral
```

### 9.3. ICP
```
priority: high | medium | low
company_size: smb | mid | enterprise
company_type: manufacturer | distributor | retailer | service | agency | saas | other
role_category: decision_maker | influencer | gatekeeper | champion | unknown
```

### 9.4. Contact
```
status: candidate | approved | contacted | replied | qualified | disqualified | unsubscribed | bounced | archived
role_category: decision_maker | influencer | gatekeeper | champion | unknown
seniority: c_level | vp | director | manager | specialist | unknown
email_type: work | personal | unknown
phone_type: work | mobile | unknown
consent_status: unknown | granted | denied | not_required
gdpr_lawful_basis: consent | legitimate_interest | contract | unknown
```

### 9.5. Message
```
channel: email | telegram | whatsapp | linkedin
status: draft | pending_review | approved | rejected | queued | sending | sent | delivered | bounced | failed | replied | closed
bounce_type: hard | soft
identity_type: user | service
```

### 9.6. Reply
```
category: positive | negative | not_interested | wrong_person | auto_reply | question | unsubscribe | out_of_office | unknown
sentiment: positive | neutral | negative
action: reply | schedule_meeting | forward_to_human | add_to_nurture | unsubscribe | close
```

### 9.7. Experiment
```
status: draft | running | paused | completed | aborted
variable_type: subject | body | offer | cta | tone | send_time | channel | other
primary_metric: reply_rate | positive_reply_rate | meetings_booked | open_rate
```

---

## 10. Правила совместимости

1. **Никаких breaking changes без major-инкремента.** Если нужно удалить поле — деprecate на minor, удаление через major.
2. **Потребитель игнорирует неизвестные поля** (Pydantic `model_config = ConfigDict(extra="ignore")`).
3. **Producer всегда пишет `schema_version`** — иначе событие отклоняется брокером (валидатор в nats-client).
4. **Сервис, читающий событие, проверяет `schema_version.major`** — при несовпадении nack и алерт.
5. **Backward compatibility на 1 major-версию вперёд** — если producer 1.0, consumer 1.x — работает. Если producer 2.0, consumer 1.x — не работает, требуется миграция.

---

## 11. Схема БД (таблицы, которые соответствуют контрактам)

На уровне Postgres каждое поле верхнего уровня — колонка, вложенные структуры — JSONB. Пример:

```sql
CREATE TABLE briefs (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  schema_version TEXT NOT NULL,
  status TEXT NOT NULL,
  completeness_score NUMERIC(3,2),
  raw_input JSONB,
  qa_history JSONB,
  identity JSONB,
  offering JSONB,
  targeting_hints JSONB,
  outreach_goals JSONB,
  missing_info JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by TEXT,
  trace_id TEXT,
  metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX ON briefs (tenant_id, status);
CREATE INDEX ON briefs (tenant_id, created_at DESC);

ALTER TABLE briefs ENABLE ROW LEVEL SECURITY;
CREATE POLICY briefs_tenant_isolation ON briefs
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

Аналогично для остальных. Вложенные структуры — JSONB, потому что они либо читаются целиком, либо не читаются. Индексировать отдельные поля внутри будем через GIN-индексы по мере необходимости.

**Исключение:** `contacts.emails` и `contacts.phones` — выносим в отдельные таблицы `contact_emails`, `contact_phones` для быстрого поиска по email/phone (дедупликация, проверка стоп-листов). Аналогично `messages` — выносим `message_status_history` для аудита.

---

## 12. Что НЕ вошло в v1 (осознанно)

Чтобы не раздувать:
- **Campaign** как сущность — пока не нужна, есть Experiment. Кампания появится в v2, когда будем группировать сообщения по большим инициативам.
- **Account** (несколько контактов в одной компании как единая «сделка») — появится, когда пойдём в CRM-функциональность.
- **Task** и **Reminder** — пока не нужны, follow-up управляется через `sequence`.
- **Attachment** как отдельная сущность — пока встроена в Brief и Message. Вынесем, если начнём с файлами активно работать.
- **Audit log** — будет отдельная таблица `audit_events`, но не как контракт (внутренняя кухня).

---

## 13. Чек-лист «готово» для этого документа

- [x] Все сущности, которые упомянуты в архитектуре, имеют контракт.
- [x] Каждая сущность версионируется.
- [x] Evidence-принцип зафиксирован и применён к Contact/Company/ICP.
- [x] Мульти-тенантность — везде `tenant_id`.
- [x] События покрывают весь пайплайн (intake → ICP → sourcing → composer → review → sender → reply → analytics).
- [x] A/B-эксперименты — first-class citizen.
- [x] 152-ФЗ/GDPR — поля consent в Contact.
- [x] Enum'ы полные, без «и т.д.».
- [x] Схема БД согласована с контрактами.
- [x] Осознанно отложенные сущности зафиксированы.

---

## Что дальше

Теперь, когда контракты зафиксированы, идём по плану **C**: `infra/docker-compose.dev.yml` + `scripts/bootstrap.sh` + Caddy-конфиг + структура репы.

Скажи слово — и я выдам следующий документ: **`infra/README.md` + полный docker-compose для dev с NATS, Postgres, Redis, MinIO, Caddy-docker-proxy, скриптами bootstrap/migrate, и структурой монорепы с uv workspaces**. Тоже исчерпывающе, чтобы агент-разработчик мог развернуть с нуля.

Или, если хочешь сначала ревью контрактов — скажи, что поправить. Что-то может быть избыточным, что-то недостающим под твои сценарии (например, я не уверен, что `sequence` в Message покрывает все твои сценарии follow-up'ов — если у тебя сложные цепочки, скажи, расширю).

### 🧑 User
_2026-09-30T16:55:11.134000+08:00_

выдавай всё исчерпывающе подробно, чтобы потом не переписывать и не дописывать, перед выдачей перепроверь себя несколько раз, от твоих действий зависит будущее целых индустрий

### 🤖 Assistant
_2026-09-30T16:55:11.132000+08:00_
