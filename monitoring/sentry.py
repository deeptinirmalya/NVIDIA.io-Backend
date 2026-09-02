import logging

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from core.config import settings

logger = logging.getLogger(__name__)


def init_sentry():
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.PYTHON_ENV or "development",
            integrations=[FastApiIntegration()],
            traces_sample_rate=1.0,
            send_default_pii=True,
        )
        logger.info("Sentry initialization completed successfully")
    else:
        logger.info("Sentry DSN not found, running without Sentry")
