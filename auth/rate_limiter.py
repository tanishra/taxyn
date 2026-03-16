from datetime import datetime, UTC

from agent.interfaces import MemoryRepositoryInterface


class RateLimitExceeded(Exception):
    pass


class RateLimiter:
    def __init__(self, repo: MemoryRepositoryInterface):
        self._repo = repo

    async def check(self, scope: str, actor: str, limit: int, window_seconds: int) -> None:
        now = datetime.now(UTC).timestamp()
        key = f"ratelimit:{scope}:{actor}"
        payload = await self._repo.get(key)
        timestamps = payload.get("timestamps", []) if isinstance(payload, dict) else []
        valid_after = now - window_seconds
        recent = [ts for ts in timestamps if isinstance(ts, (int, float)) and ts >= valid_after]

        if len(recent) >= limit:
            raise RateLimitExceeded(f"Rate limit exceeded for {scope}. Try again later.")

        recent.append(now)
        await self._repo.set(key, {"timestamps": recent}, tags="ratelimit")
