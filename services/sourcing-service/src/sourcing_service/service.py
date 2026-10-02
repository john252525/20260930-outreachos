"""Search orchestrator: the core OSINT pipeline."""

import asyncio
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from common.errors import AppError, NotFoundError
from nats_client.publisher import Publisher
from sourcing_service import events
from sourcing_service.clients.contact_store_client import ContactStoreClient
from sourcing_service.clients.icp_client import ICPClient
from sourcing_service.config import Settings
from sourcing_service.connectors.base import RawCandidate, SearchCriteria
from sourcing_service.connectors.registry import ConnectorRegistry
from sourcing_service.models import SearchJob, SearchJobItem
from sourcing_service.normalization.normalizer import Normalizer
from sourcing_service.repository import SearchJobRepository
from sourcing_service.scoring.scorer import Scorer

logger = structlog.get_logger()


class SearchOrchestrator:
    def __init__(
        self,
        repo: SearchJobRepository,
        icp_client: ICPClient,
        contact_store: ContactStoreClient,
        registry: ConnectorRegistry,
        normalizer: Normalizer,
        scorer: Scorer,
        publisher: Publisher,
        settings: Settings,
        running_tasks: dict[str, asyncio.Task[None]],
    ) -> None:
        self._repo = repo
        self._icp = icp_client
        self._store = contact_store
        self._registry = registry
        self._normalizer = normalizer
        self._scorer = scorer
        self._publisher = publisher
        self._settings = settings
        self._running_tasks = running_tasks

    async def create_and_run(
        self,
        *,
        tenant_id: UUID,
        icp_id: UUID,
        segment_id: str,
        sources: list[str] | None,
        limit_per_source: int | None,
        urls: list[str] | None = None,
        trace_id: str = "",
    ) -> SearchJob:
        # Persist the job in its own committed session so the background task can
        # see it immediately (avoids a race with the request transaction).
        from db.rls import set_tenant_context
        from db.session import async_session_factory

        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            job = SearchJob(
                tenant_id=tenant_id,
                icp_id=icp_id,
                segment_id=segment_id,
                brief_id="",
                status="pending",
                params={
                    "sources": sources or self._registry.list_available(),
                    "limit_per_source": limit_per_source
                    or self._settings.max_candidates_per_source,
                    **({"urls": urls} if urls else {}),
                },
                progress={},
                trace_id=trace_id,
            )
            session.add(job)
            await session.flush()
            await session.refresh(job)

        await events.emit_contacts_search_started(
            self._publisher, job, sources=job.params["sources"], trace_id=trace_id
        )

        task = asyncio.create_task(self._run_job(job.id, tenant_id=tenant_id, trace_id=trace_id))
        self._running_tasks[str(job.id)] = task
        task.add_done_callback(lambda _t: self._running_tasks.pop(str(job.id), None))
        return job

    async def _run_job(self, job_id: UUID, *, tenant_id: UUID, trace_id: str) -> None:
        try:
            await asyncio.wait_for(
                self._run_job_inner(job_id, tenant_id=tenant_id, trace_id=trace_id),
                timeout=self._settings.job_timeout_seconds,
            )
        except TimeoutError:
            await self._mark_failed(job_id, tenant_id, "timeout", "timeout")
        except asyncio.CancelledError:
            await self._mark_cancelled(job_id, tenant_id)
            raise

    async def _run_job_inner(self, job_id: UUID, *, tenant_id: UUID, trace_id: str) -> None:
        from db.rls import set_tenant_context
        from db.session import async_session_factory

        started = time.monotonic()
        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            repo = SearchJobRepository(session)
            job = await repo.get(job_id)
            if job is None:
                logger.error("search_job_not_found", job_id=str(job_id))
                return
            try:
                job.status = "running"
                job.started_at = datetime.now(UTC)
                await session.flush()

                icp = await self._icp.get_icp(
                    str(job.icp_id), tenant_id=str(tenant_id), trace_id=trace_id
                )
                job.brief_id = icp.get("brief_id", "")
                segments = icp.get("payload", {}).get("segments", [])
                segment = next((s for s in segments if s.get("id") == job.segment_id), None)
                if segment is None:
                    raise AppError(
                        f"Segment {job.segment_id} not found in ICP",
                        code="segment_not_found",
                        status_code=400,
                    )

                criteria = self._build_criteria(segment, job.params)
                sources = job.params.get("sources", [])
                available = [s for s in sources if s in self._registry.list_available()]

                job.progress = {
                    "stage": "sourcing",
                    "sources_done": 0,
                    "sources_total": len(available),
                    "candidates_raw": 0,
                }
                await session.flush()

                all_candidates: list[RawCandidate] = []
                seen_keys: set[str] = set()
                total_cost = 0.0
                for source_name in available[: self._settings.max_sources_per_search]:
                    try:
                        connector = self._registry.get(source_name)
                        result = await connector.search(criteria)
                        total_cost += result.cost_usd
                        for cand in result.candidates:
                            key = cand.dedup_key()
                            if key in seen_keys:
                                continue
                            seen_keys.add(key)
                            all_candidates.append(cand)
                    except Exception as e:
                        logger.warning("connector_failed", source=source_name, error=str(e))
                    job.progress = {
                        **job.progress,
                        "sources_done": job.progress.get("sources_done", 0) + 1,
                        "candidates_raw": len(all_candidates),
                    }
                    await session.flush()

                job.candidates_raw_count = len(all_candidates)
                job.progress = {
                    **job.progress,
                    "stage": "normalizing",
                    "candidates_normalized": 0,
                }
                await session.flush()

                items: list[SearchJobItem] = []
                for cand in all_candidates:
                    item = SearchJobItem(
                        tenant_id=tenant_id,
                        job_id=job.id,
                        source=cand.source,
                        source_url=cand.source_url,
                        raw_payload={
                            "title": cand.title,
                            "snippet": cand.snippet,
                            "domain": cand.domain,
                            "raw": cand.raw_payload,
                        },
                        status="raw",
                    )
                    session.add(item)
                    items.append(item)
                await session.flush()

                segment_context = self._segment_to_context(segment)
                normalized_results = await self._normalizer.normalize_batch(
                    all_candidates,
                    tenant_id=tenant_id,
                    segment_context=segment_context,
                    max_concurrency=self._settings.max_parallel_llm,
                )
                norm_map: dict[str, tuple[Any, Any]] = {}
                for cand, res, err in normalized_results:
                    norm_map[cand.dedup_key()] = (res, err)

                job.progress = {**job.progress, "stage": "scoring"}
                await session.flush()

                normalized_count = 0
                persisted_count = 0
                companies_created = 0
                companies_merged = 0
                contacts_created = 0
                contacts_merged = 0

                for item, cand in zip(items, all_candidates, strict=False):
                    res, err = norm_map.get(cand.dedup_key(), (None, "unknown"))
                    if res is None or err:
                        item.status = "failed"
                        item.error = err
                        continue
                    if not res.is_company or not res.is_relevant:
                        item.status = "skipped"
                        item.skip_reason = "not_relevant" if res.is_company else "not_company"
                        continue
                    normalized_count += 1
                    item.normalized_company = res.company
                    item.normalized_contacts = [c.model_dump() for c in res.contacts]
                    item.status = "normalized"
                    score, breakdown, _ = self._scorer.score(
                        normalized_company=res.company,
                        contacts=item.normalized_contacts or [],
                        segment=segment,
                    )
                    item.score = score
                    item.score_breakdown = breakdown
                    if score < self._settings.min_score_threshold:
                        item.status = "skipped"
                        item.skip_reason = f"low_score:{score:.2f}"
                        continue
                    item.status = "scored"
                job.candidates_normalized_count = normalized_count
                job.progress = {
                    **job.progress,
                    "stage": "persisting",
                    "candidates_normalized": normalized_count,
                    "candidates_persisted": 0,
                }
                await session.flush()

                for item in items:
                    if item.status != "scored" or not item.normalized_company:
                        continue
                    try:
                        company_payload = self._build_company_payload(
                            item.normalized_company, item.source_url
                        )
                        company, action = await self._store.upsert_company(
                            tenant_id=str(tenant_id),
                            payload=company_payload,
                            trace_id=trace_id,
                            idempotency_key=f"sourcing:{job.id}:company:{item.id}",
                        )
                        item.company_id = UUID(company["id"]) if company else None
                        if action == "created":
                            companies_created += 1
                        else:
                            companies_merged += 1

                        contact_ids: list[str] = []
                        for c in item.normalized_contacts or []:
                            contact_payload = self._build_contact_payload(
                                c, item.source_url, company_id=item.company_id
                            )
                            contact, c_action = await self._store.upsert_contact(
                                tenant_id=str(tenant_id),
                                payload=contact_payload,
                                trace_id=trace_id,
                                idempotency_key=(
                                    f"sourcing:{job.id}:contact:{item.id}:{c.get('full_name')}"
                                ),
                            )
                            if contact is None:
                                continue
                            contact_ids.append(contact["id"])
                            if c_action == "created":
                                contacts_created += 1
                            else:
                                contacts_merged += 1
                        item.contact_ids = contact_ids
                        item.status = "persisted"
                        persisted_count += 1
                        job.progress = {
                            **job.progress,
                            "candidates_persisted": persisted_count,
                        }
                        await session.flush()
                    except Exception as e:
                        logger.exception("persist_failed", item_id=str(item.id))
                        item.status = "failed"
                        item.error = str(e)

                job.candidates_persisted_count = persisted_count
                job.companies_created = companies_created
                job.companies_merged = companies_merged
                job.contacts_created = contacts_created
                job.contacts_merged = contacts_merged
                job.total_cost_usd = total_cost
                job.duration_ms = int((time.monotonic() - started) * 1000)
                job.status = "completed"
                job.finished_at = datetime.now(UTC)
                job.progress = {**job.progress, "stage": "done"}
                await session.flush()

                await events.emit_contacts_found(
                    self._publisher,
                    job,
                    count=persisted_count,
                    company_ids=[str(i.company_id) for i in items if i.company_id],
                    trace_id=trace_id,
                )
                logger.info(
                    "search_job_completed",
                    job_id=str(job.id),
                    raw=len(all_candidates),
                    normalized=normalized_count,
                    persisted=persisted_count,
                    companies_created=companies_created,
                    contacts_created=contacts_created,
                    cost_usd=total_cost,
                    duration_ms=job.duration_ms,
                )
            except Exception as e:
                logger.exception("search_job_failed", job_id=str(job_id))
                job.status = "failed"
                job.error = str(e)
                job.error_stage = job.progress.get("stage")
                job.finished_at = datetime.now(UTC)
                job.duration_ms = int((time.monotonic() - started) * 1000)
                await session.flush()

    async def _mark_failed(self, job_id: UUID, tenant_id: UUID, error: str, stage: str) -> None:
        from db.rls import set_tenant_context
        from db.session import async_session_factory

        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            job = await session.get(SearchJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error = error
                job.error_stage = stage
                job.finished_at = datetime.now(UTC)
                await session.flush()

    async def _mark_cancelled(self, job_id: UUID, tenant_id: UUID) -> None:
        from db.rls import set_tenant_context
        from db.session import async_session_factory

        async with async_session_factory() as session, session.begin():
            await set_tenant_context(session, tenant_id)
            job = await session.get(SearchJob, job_id)
            if job is not None and job.status in ("pending", "running"):
                job.status = "cancelled"
                job.finished_at = datetime.now(UTC)
                await session.flush()

    def _build_criteria(self, segment: dict[str, Any], params: dict[str, Any]) -> SearchCriteria:
        firm = segment.get("firmographic", {})
        industries = firm.get("industries", []) or []
        sub = firm.get("sub_industries", []) or []
        geos = firm.get("geos", []) or []
        roles = segment.get("roles_to_contact", []) or []

        keywords: list[str] = []
        for ind in industries[:3]:
            keywords.append(ind)
        for s in sub[:2]:
            keywords.append(f"{industries[0]} {s}" if industries else s)
        for r in roles[:1]:
            role_title = r.get("role_title")
            if role_title and industries:
                keywords.append(f"{industries[0]} {role_title}")
        if not keywords:
            keywords = ["компания"]

        extra: dict[str, Any] = {}
        if params.get("urls"):
            extra["urls"] = params["urls"]
        return SearchCriteria(
            keywords=keywords,
            geo=geos or ["RU"],
            language=params.get("language", "ru"),
            limit=params.get("limit_per_source", 50),
            extra=extra,
        )

    def _segment_to_context(self, segment: dict[str, Any]) -> str:
        firm = segment.get("firmographic", {})
        parts = [
            f"Название: {segment.get('name', '')}",
            f"Описание: {segment.get('description', '')}",
            f"Отрасли: {', '.join(firm.get('industries', []))}",
            f"Размер: {', '.join(firm.get('company_sizes', []))}",
            f"Гео: {', '.join(firm.get('geos', []))}",
        ]
        return "\n".join(p for p in parts if p.split(": ", 1)[-1])

    def _build_company_payload(
        self, company: dict[str, Any], source_url: str | None
    ) -> dict[str, Any]:
        def _fact(v: Any) -> dict[str, Any]:
            if isinstance(v, dict) and "value" in v:
                return v
            return {"value": v, "confidence": 0.5, "evidence": []}

        payload = {
            "name": _fact(company.get("name")),
            "domain": _fact(company.get("domain")),
            "website": _fact(company.get("website")),
            "industry": _fact(company.get("industry")),
            "sub_industry": _fact(company.get("sub_industry")),
            "locations": company.get("locations") or [],
        }
        if company.get("registry_ids"):
            payload["registry_ids"] = company["registry_ids"]
        return payload

    def _build_contact_payload(
        self, contact: dict[str, Any], source_url: str | None, company_id: UUID | None
    ) -> dict[str, Any]:
        full_name = contact.get("full_name", "")
        payload: dict[str, Any] = {
            "full_name": {
                "value": full_name,
                "confidence": contact.get("confidence", 0.5),
                "evidence": [],
            },
            "role_category": contact.get("role_category", "unknown"),
            "seniority": contact.get("seniority", "unknown"),
            "emails": contact.get("emails", []),
            "phones": contact.get("phones", []),
            "company_id": str(company_id) if company_id else None,
        }
        if contact.get("position"):
            payload["position"] = {
                "value": contact["position"],
                "confidence": contact.get("confidence", 0.5),
                "evidence": [],
            }
        return payload

    async def get(self, job_id: UUID) -> SearchJob:
        job = await self._repo.get(job_id)
        if job is None:
            raise NotFoundError(f"Search job {job_id} not found")
        return job

    async def list(
        self, *, tenant_id: UUID, status: str | None, limit: int, offset: int
    ) -> list[SearchJob]:
        return await self._repo.list(tenant_id=tenant_id, status=status, limit=limit, offset=offset)

    async def cancel(self, *, job_id: UUID, tenant_id: UUID, trace_id: str) -> SearchJob:
        job = await self._repo.get(job_id)
        if job is None:
            raise NotFoundError(f"Search job {job_id} not found")
        if job.status in ("completed", "failed", "cancelled"):
            return job
        task = self._running_tasks.get(str(job_id))
        if task is not None:
            task.cancel()
        job.status = "cancelled"
        job.finished_at = datetime.now(UTC)
        await self._repo.session.flush()
        await self._repo.session.refresh(job)
        return job

    async def retry_failed(self, *, job_id: UUID, tenant_id: UUID, trace_id: str) -> SearchJob:
        """Retry normalization+persist for failed items of a job."""
        job = await self._repo.get(job_id)
        if job is None:
            raise NotFoundError(f"Search job {job_id} not found")

        from sqlalchemy import select

        session = self._repo.session
        items = list(
            (
                await session.execute(
                    select(SearchJobItem).where(
                        SearchJobItem.job_id == job.id, SearchJobItem.status == "failed"
                    )
                )
            )
            .scalars()
            .all()
        )
        if not items:
            return job

        segments = []
        try:
            icp = await self._icp.get_icp(
                str(job.icp_id), tenant_id=str(tenant_id), trace_id=trace_id
            )
            segments = icp.get("payload", {}).get("segments", [])
        except Exception as e:
            logger.warning("retry_icp_fetch_failed", error=str(e))
        segment = next((s for s in segments if s.get("id") == job.segment_id), None) or {}
        segment_context = self._segment_to_context(segment)

        for item in items:
            raw = item.raw_payload or {}
            cand = RawCandidate(
                source=item.source,
                source_url=item.source_url,
                title=raw.get("title"),
                snippet=raw.get("snippet"),
                domain=raw.get("domain"),
                raw_payload=raw.get("raw", {}) or {},
            )
            try:
                res = await self._normalizer.normalize(
                    cand, tenant_id=tenant_id, segment_context=segment_context
                )
                if not res.is_company or not res.is_relevant:
                    item.status = "skipped"
                    item.skip_reason = "not_relevant"
                    continue
                item.normalized_company = res.company
                item.normalized_contacts = [c.model_dump() for c in res.contacts]
                score, breakdown, _ = self._scorer.score(
                    normalized_company=res.company,
                    contacts=item.normalized_contacts or [],
                    segment=segment,
                )
                item.score = score
                item.score_breakdown = breakdown
                if score < self._settings.min_score_threshold:
                    item.status = "skipped"
                    item.skip_reason = f"low_score:{score:.2f}"
                    continue
                company_payload = self._build_company_payload(res.company, item.source_url)
                company, _action = await self._store.upsert_company(
                    tenant_id=str(tenant_id),
                    payload=company_payload,
                    trace_id=trace_id,
                    idempotency_key=f"sourcing:{job.id}:company:{item.id}:retry",
                )
                item.company_id = UUID(company["id"]) if company else None
                item.status = "persisted"
                item.error = None
            except Exception as e:
                item.error = str(e)
                logger.warning("retry_item_failed", item_id=str(item.id), error=str(e))
        await session.flush()
        await session.refresh(job)
        return job

    async def stats(self, *, tenant_id: UUID, period_days: int) -> dict[str, Any]:
        from sqlalchemy import text

        session = self._repo.session
        row = (
            (
                await session.execute(
                    text(
                        """
                    SELECT
                      COUNT(*) AS total,
                      COUNT(*) FILTER (WHERE status='completed') AS completed,
                      COUNT(*) FILTER (WHERE status='failed') AS failed,
                      COALESCE(SUM(candidates_raw_count),0) AS raw,
                      COALESCE(SUM(candidates_persisted_count),0) AS persisted,
                      COALESCE(SUM(companies_created),0) AS companies,
                      COALESCE(SUM(contacts_created),0) AS contacts,
                      COALESCE(SUM(total_cost_usd),0) AS cost,
                      COALESCE(AVG(duration_ms) FILTER (WHERE duration_ms IS NOT NULL),0) AS avg_duration
                    FROM search_jobs
                    WHERE tenant_id = :tid AND created_at > NOW() - make_interval(days => :days)
                    """
                    ),
                    {"tid": str(tenant_id), "days": period_days},
                )
            )
            .mappings()
            .one()
        )

        by_source_rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT source,
                      COUNT(*) AS items,
                      COUNT(*) FILTER (WHERE status='persisted') AS persisted
                    FROM search_job_items
                    WHERE tenant_id = :tid AND created_at > NOW() - make_interval(days => :days)
                    GROUP BY source
                    """
                    ),
                    {"tid": str(tenant_id), "days": period_days},
                )
            )
            .mappings()
            .all()
        )

        by_status_rows = (
            (
                await session.execute(
                    text(
                        """
                    SELECT status, COUNT(*) AS cnt FROM search_jobs
                    WHERE tenant_id = :tid AND created_at > NOW() - make_interval(days => :days)
                    GROUP BY status
                    """
                    ),
                    {"tid": str(tenant_id), "days": period_days},
                )
            )
            .mappings()
            .all()
        )

        raw = int(row["raw"])
        persisted = int(row["persisted"])
        return {
            "period_days": period_days,
            "total_jobs": int(row["total"]),
            "completed_jobs": int(row["completed"]),
            "failed_jobs": int(row["failed"]),
            "total_candidates_raw": raw,
            "total_candidates_persisted": persisted,
            "total_companies_created": int(row["companies"]),
            "total_contacts_created": int(row["contacts"]),
            "total_cost_usd": float(row["cost"]),
            "avg_duration_ms": int(row["avg_duration"]),
            "avg_yield_percent": round((persisted / raw * 100) if raw else 0.0, 2),
            "by_source": {
                r["source"]: {"items": int(r["items"]), "persisted": int(r["persisted"])}
                for r in by_source_rows
            },
            "by_status": {r["status"]: int(r["cnt"]) for r in by_status_rows},
        }
