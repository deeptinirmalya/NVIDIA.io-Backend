import logging
from posthog import Posthog
from core.config import settings

logger = logging.getLogger("posthog")

class DummyPosthog:
    def capture(self, *args, **kwargs):
        logger.debug(f"[DummyPosthog] Capture event: args={args}, kwargs={kwargs}")

    def identify(self, *args, **kwargs):
        logger.debug(f"[DummyPosthog] Identify user: args={args}, kwargs={kwargs}")

if settings.POSTHOG_PROJECT_KEY:
    posthog = Posthog(
        project_api_key=settings.POSTHOG_PROJECT_KEY,
        host="https://us.posthog.com",  
    )
else:
    logger.info("PostHog key not configured. Fallback to DummyPosthog 🦔")
    posthog = DummyPosthog()
