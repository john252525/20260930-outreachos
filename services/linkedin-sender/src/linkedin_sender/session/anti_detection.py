"""Human-like behaviour helpers for LinkedIn automation."""

import asyncio
import random

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]


class HumanBehavior:
    @staticmethod
    async def random_delay(min_sec: float = 2.0, max_sec: float = 8.0) -> None:
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    @staticmethod
    async def typing_pause() -> None:
        await asyncio.sleep(random.uniform(1.5, 4.0))

    @staticmethod
    def random_user_agent() -> str:
        return random.choice(USER_AGENTS)
