# Спринт 1 — `brief-service` (intake + LLM-интервью)
Проверил: зависимости от Спринта 0 (контракты, db, nats-client, common, llm-gateway) соблюдены, 
порядок задач логичен, acceptance criteria проверяемы, нет противоречий с `docs/contracts.md` и 
`docs/infra.md`. Каждая задача самодостаточна.
## Что такое `brief-service` и почему он важный
Это первый «умный» сервис платформы. Он превращает **сырой ввод** (текст, ссылку, ответы, 
транскрипт) в **структурированный Brief v1**, из которого потом строится ICP и весь outreach. От 
качества этого шага зависит всё дальше: плохой бриф → плохой ICP → мусорный sourcing → письма в 
молоко. Ключевая идея: **адаптивный intake**. Минимум данных от пользователя, дальше LLM задаёт 
уточняющие вопросы по одному, пока не наберётся достаточная полнота (`completeness_score >= 0.85`).
## Архитектура сервиса (что внутри)
``` ┌─────────────────────────────────┐ │ brief-service │ │ │ HTTP POST /briefs ──►│ API layer 
  (routes) │
                      │ │ │ │ ▼ │ │ BriefService (бизнес-логика) │ │ │ │ │ ├──► BriefRepository │ │ 
                      ├──► QuestionGenerator ───┼──► llm-gateway │ ├──► BriefExtractor ──────┼──► 
                      llm-gateway │ ├──► CompletenessScorer │ │ └──► Publisher (NATS) │ │ │ │ 
                      Events: │ │ - brief.created │ │ - brief.questions_asked │ │ - brief.updated │ 
                      │ - brief.completed │ └─────────────────────────────────┘
``` **Что сервис делает:** 1. Принимает raw input (текст, URL, файлы, транскрипт). 2. Извлекает 
через LLM структурированные поля Brief (identity, offering, targeting_hints, outreach_goals). 3. 
Считает `completeness_score`. 4. Если не хватает данных — генерирует уточняющие вопросы, по одному 
на итерацию. 5. Принимает ответы, обновляет Brief. 6. Когда `completeness_score >= 0.85` — переводит 
в `complete` и публикует `brief.completed`. **Что НЕ делает (осознанно):** - Не строит ICP — это 
задача `icp-service` (Спринт 2). - Не ищет контакты — это `sourcing-service` (Спринт 2). - Не 
генерирует письма — это `composer-service` (Спринт 3). - Не имеет UI — только API. ---
