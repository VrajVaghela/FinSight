from __future__ import annotations

import asyncio

from backend.retrieval.section_router import SectionMatch
from backend.retrieval.session_scoper import SessionScoper


class FakeRedis:
    def __init__(self):
        self.sets = {}
        self.values = {}

    async def smembers(self, key):
        return self.sets.get(key, set())

    async def sadd(self, key, value):
        self.sets.setdefault(key, set()).add(value)

    async def expire(self, key, ttl):
        return True

    async def scard(self, key):
        return len(self.sets.get(key, set()))

    async def setex(self, key, ttl, value):
        self.values[key] = value

    async def get(self, key):
        return self.values.get(key)

    async def ttl(self, key):
        return 100

    async def delete(self, *keys):
        for key in keys:
            self.sets.pop(key, None)
            self.values.pop(key, None)


def section(section_id: str, score: float) -> SectionMatch:
    return SectionMatch(section_id, section_id, 1, "file", 1, 1, 1, 0, 0, score, "")


def test_session_scope_bias_boosts_active_section():
    scoper = SessionScoper(FakeRedis())
    asyncio.run(scoper.add_active_section("c1", "sec-a"))
    ranked = asyncio.run(scoper.score_with_scope_bias([section("sec-b", 0.2), section("sec-a", 0.1)], "c1", 0.15))
    assert ranked[0].section_id == "sec-a"
