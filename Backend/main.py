"""Backend entry point: `make backend` (uvicorn main:app --app-dir Backend)."""

import logging
import re

from engano_backend.app import create_app
from engano_backend.env import load_env


class _RedactVerifyToken(logging.Filter):
    """Meta sends the webhook verify token in the query string; keep it out of access logs."""

    _pattern = re.compile(r"(hub[._]verify_token=)[^&\s\"]+")

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            record.args = tuple(
                self._pattern.sub(r"\1***", a) if isinstance(a, str) else a for a in record.args
            )
        return True


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("uvicorn.access").addFilter(_RedactVerifyToken())
load_env()
app = create_app()
