import json
import time
import asyncio
import logging
from app.core.redis_client import get_redis_client, RedisQueue
from app.workers.campaign_worker import CampaignWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("job_worker")

class JobWorkerDaemon:
    def __init__(self):
        self.campaign_queue = RedisQueue("queue:campaigns")
        self.ai_queue = RedisQueue("queue:ai")
        self.running = True

    async def run_loop(self):
        logger.info("WhatsApp AI SaaS Background Job Worker started. Listening for tasks...")
        while self.running:
            try:
                # 1. Check campaign tasks
                raw_campaign_job = self.campaign_queue.dequeue(timeout=1)
                if raw_campaign_job:
                    data = json.loads(raw_campaign_job)
                    campaign_id = data.get("campaign_id")
                    logger.info("Processing campaign job: %s", campaign_id)
                    await CampaignWorker.process_campaign_batch(campaign_id)

                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Worker iteration exception: {e}")
                await asyncio.sleep(1)

def start_worker():
    daemon = JobWorkerDaemon()
    asyncio.run(daemon.run_loop())

if __name__ == "__main__":
    start_worker()
