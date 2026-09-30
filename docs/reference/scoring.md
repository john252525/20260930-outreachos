# reference/scoring.md — completeness-скоринг брифа

> Как считается «насколько полон бриф» и «чего не хватает». Детерминированно, без LLM.

## Зачем

`brief-service` должен понимать, когда бриф достаточно заполнен, чтобы перестать задавать вопросы,
и какие именно поля спрашивать следующими. Это арифметика — считаем кодом (быстро, бесплатно, предсказуемо).
LLM используется ТОЛЬКО для генерации formulation вопроса, но не для решения «чего не хватает».

## Где в коде

- Веса и приоритеты: `services/brief-service/src/brief_service/scoring/constants.py`
- Расчёт полноты: `services/brief-service/src/brief_service/scoring/completeness.py`
- Анализ пропусков: `services/brief-service/src/brief_service/scoring/missing_info.py`

## Модель весов

Бриф состоит из 4 групп верхнего уровня. Их веса (сумма = 1.0):

| Группа | Вес |
|---|---|
| identity | 0.25 |
| offering | 0.30 |
| targeting_hints | 0.20 |
| outreach_goals | 0.25 |

Внутри каждой группы — поля со своими весами (сумма внутри группы = 1.0):

### identity (0.25)

| Поле | Вес |
|---|---|
| project_name | 0.15 |
| company_name | 0.10 |
| company_url | 0.10 |
| one_liner | 0.15 |
| industry | 0.20 |
| sub_industry | 0.05 |
| language | 0.05 |
| geo_primary | 0.20 |

### offering (0.30)

| Поле | Вес |
|---|---|
| what_we_sell | 0.30 |
| categories | 0.15 |
| differentiators | 0.20 |
| proof_points | 0.10 |
| price_range | 0.15 |
| sales_cycle_days_estimate | 0.10 |

### targeting_hints (0.20)

| Поле | Вес |
|---|---|
| known_customers_examples | 0.20 |
| must_have_criteria | 0.30 |
| must_not_have_criteria | 0.15 |
| company_size_hint | 0.15 |
| role_hints | 0.20 |

### outreach_goals (0.25)

| Поле | Вес |
|---|---|
| primary_goal | 0.40 |
| goal_description | 0.20 |
| tone_of_voice | 0.20 |
| forbidden_topics | 0.10 |
| required_mentions | 0.10 |

## Как считается поле (0 или 1)

`_field_score` возвращает 1.0, если поле «заполнено», иначе 0.0. Правила:
- `None` → не заполнено.
- пустая/пробельная строка → не заполнено.
- пустой список/словарь → не заполнено.
- числа → заполнено.
- ОСОБЫЙ СЛУЧАЙ `offering.price_range`: заполнено, если `model != "unknown"` ИЛИ есть `min`/`max`.

## Итоговая формула

```
completeness = Σ по группам ( group_weight * Σ по полям ( field_weight * field_score ) )
```

Результат округляется до 4 знаков и ограничивается [0.0, 1.0].

## Порог и статусы

- Порог задаётся `BRIEF_COMPLETENESS_THRESHOLD` (дефолт **0.85**).
- `completeness >= threshold` → бриф `complete`, вопросы прекращаются.
- `completeness <  threshold` → `in_progress`, LLM генерирует следующий уточняющий вопрос.
- В dev порог можно понизить (например, 0.6) для быстрой отладки.
- Форсированное завершение: `POST /briefs/{id}/complete` (игнорирует порог).

## Missing info и приоритеты

`analyze_missing_info` возвращает незаполненные поля, отсортированные по приоритету:
`high` → `medium` → `low`. Для каждого поля — `field`, `why_needed`, `priority`.

Например, приоритет `high` у: `identity.project_name`, `identity.industry`, `identity.geo_primary`,
`offering.what_we_sell`, `offering.differentiators`, `targeting_hints.must_have_criteria`, `outreach_goals.primary_goal`.

`get_next_priority_field` отдаёт самое приоритетное незаполненное поле — под него генерируется следующий вопрос.

## Пример

- Пустой бриф → `completeness = 0.0`.
- Один текст без извлечённых полей → ~0.16.
- Бриф с project_name + industry + what_we_sell + primary_goal → ~0.39.
- Все поля заполнены → `1.0`.

## Менять веса

Только в `constants.py`. Если меняешь смысл (например, считаешь `differentiators` важнее `categories`) —
это влияет на все существующие брифы при пересчёте. Исторические `completeness_score` в БД не пересчитываются автоматически.
