import asyncio
import logging

logger = logging.getLogger("elastic_mock")

async def sync_to_elastic(table_id: str, state: str, date: str = None, time_slot: str = None):
    # Имитация асинхронной отправки в Elasticsearch
    await asyncio.sleep(0.05)
    logger.info(f"[Elastic] Updated table {table_id}: state={state}, date={date}, slot={time_slot}")