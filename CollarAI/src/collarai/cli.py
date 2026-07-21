from __future__ import annotations

import argparse
import asyncio
from time import perf_counter

from collarai.models import RunStatus
from collarai.query import QueryRouter, format_answer
from collarai.service import build_service


async def run_demo(query: str) -> None:
    service = build_service()
    try:
        routed = await QueryRouter().parse(query)
        started = perf_counter()
        result = await service.analyze_financing_transactions(routed.request)
        elapsed_ms = round((perf_counter() - started) * 1_000)
        if result.status is RunStatus.COMPLETE:
            print(format_answer(query, result, elapsed_ms).model_dump_json(indent=2))
        else:
            print(result.model_dump_json(indent=2))
    finally:
        await service.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a CollarAI research question")
    parser.add_argument("query", nargs="?", default="What is Nvidia's IPO amount?")
    args = parser.parse_args()
    asyncio.run(run_demo(args.query))


if __name__ == "__main__":
    main()
