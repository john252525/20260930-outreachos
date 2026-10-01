"""Read-only NATS JetStream inspector."""

import contextlib
import json
import uuid
from typing import Any

from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext

from nats_client.streams import STREAMS


class NATSViewer:
    """Reads stream stats and recent messages (does not modify streams)."""

    def __init__(self, nc: NATSClient) -> None:
        self._nc = nc
        self._js: JetStreamContext = nc.jetstream()

    async def streams(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for cfg in STREAMS:
            try:
                info = await self._js.stream_info(cfg.name)
                state = info.state
                result.append(
                    {
                        "name": cfg.name,
                        "subjects": cfg.subjects,
                        "messages": state.messages,
                        "bytes": state.bytes,
                        "consumers": state.consumer_count,
                    }
                )
            except Exception as e:
                result.append({"name": cfg.name, "error": str(e)})
        return result

    async def recent_messages(
        self, *, stream: str, subject: str = ">", limit: int = 25
    ) -> list[dict[str, Any]]:
        """Fetch up to `limit` messages from a stream using a throwaway consumer."""
        consumer = f"console_{uuid.uuid4().hex[:12]}"
        messages: list[dict[str, Any]] = []
        try:
            sub = await self._js.pull_subscribe(
                subject=subject,
                durable=consumer,
                stream=stream,
            )
        except Exception as e:
            return [{"error": str(e)}]

        try:
            for _ in range(3):
                try:
                    fetched = await sub.fetch(limit - len(messages), timeout=1)
                except Exception:
                    break
                if not fetched:
                    break
                for msg in fetched:
                    envelope: Any
                    try:
                        envelope = json.loads(msg.data)
                    except Exception:
                        envelope = {"raw": msg.data.decode(errors="replace")}
                    messages.append(
                        {
                            "subject": msg.subject,
                            "event_type": envelope.get("event_type"),
                            "occurred_at": envelope.get("occurred_at"),
                            "producer": envelope.get("producer"),
                            "tenant_id": envelope.get("tenant_id"),
                            "trace_id": envelope.get("trace_id"),
                            "payload": envelope.get("payload"),
                        }
                    )
                    await msg.ack()
                if len(messages) >= limit:
                    break
        finally:
            with contextlib.suppress(Exception):
                await self._js.delete_consumer(stream, consumer)
        messages.reverse()  # newest first
        return messages[:limit]
