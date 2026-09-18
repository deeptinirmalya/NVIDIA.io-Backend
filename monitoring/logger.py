import logging
import json
import time
import queue
import threading
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from core.config import settings
from monitoring.middleware import request_id_var

class JSONFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=ZoneInfo("Asia/Kolkata"))
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        

        req_id = request_id_var.get()
        if req_id:
            log_data["request_id"] = req_id

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        standard_attrs = {
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'levelname', 'levelno', 'lineno', 'module',
            'msecs', 'message', 'msg', 'name', 'pathname', 'process',
            'processName', 'relativeCreated', 'stack_info', 'thread',
            'threadName'
        }
        
        for key, value in record.__dict__.items():
            if key not in standard_attrs:
                log_data[key] = value
                
        return json.dumps(log_data, default=str)

class DevelopmentFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[41m', # Red background
    }
    RESET = '\033[0m'

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, tz=ZoneInfo("Asia/Kolkata"))
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, '')
        level_str = f"{color}[{record.levelname}]{self.RESET}"
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        message = record.getMessage()
        
        req_id = request_id_var.get()
        req_id_prefix = f" [ReqID: {req_id}]" if req_id else ""
        log_line = f"{timestamp} {level_str}{req_id_prefix} [{record.name}] {message}"
        
        if record.exc_info:
            log_line += f"\n{self.formatException(record.exc_info)}"
            
        return log_line

class LokiHandler(logging.Handler):
    def __init__(self, loki_url: str, username: str | None = None, password: str | None = None):
        super().__init__()
        self.loki_url = loki_url
        self.username = username
        self.password = password
        self.queue = queue.Queue()
        self.session = requests.Session()
        if username and password:
            self.session.auth = (username, password)
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.queue.put((time.time_ns(), log_entry, record))
        except Exception:
            self.handleError(record)

    def _worker(self):
        while True:
            try:
                batch = []
                item = self.queue.get()
                batch.append(item)
                
                time.sleep(0.05)
                while not self.queue.empty() and len(batch) < 100:
                    batch.append(self.queue.get_nowait())

                streams = {}
                for ns, msg, record in batch:
                    level = getattr(record, 'levelname', 'INFO')
                    logger_name = getattr(record, 'name', 'root')
                    labels_key = (level, logger_name)
                    if labels_key not in streams:
                        streams[labels_key] = []
                    streams[labels_key].append([str(ns), msg])

                payload = {
                    "streams": [
                        {
                            "stream": {
                                "level": level.lower(),
                                "logger": logger,
                                "environment": settings.PYTHON_ENV or "development",
                                "service": settings.PROJECT_NAME.lower().replace(" ", "-")
                            },
                            "values": values
                        }
                        for (level, logger), values in streams.items()
                    ]
                }

                try:
                    response = self.session.post(
                        self.loki_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=5
                    )
                    if response.status_code >= 400:
                        import sys
                        print(f"Loki push failed: {response.status_code} {response.text}", file=sys.stderr)
                except Exception as e:
                    import sys
                    print(f"Error sending logs to Loki: {e}", file=sys.stderr)
                finally:
                    for _ in batch:
                        self.queue.task_done()
            except Exception as e:
                import sys
                print(f"Loki handler thread error: {e}", file=sys.stderr)

def setup_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        
    console_handler = logging.StreamHandler()
    if settings.PYTHON_ENV == "production":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(DevelopmentFormatter())
    root_logger.addHandler(console_handler)
    
    if settings.LOKI_URL:
        loki_handler = LokiHandler(
            loki_url=settings.LOKI_URL,
            username=settings.LOKI_USERNAME,
            password=settings.LOKI_PASSWORD
        )
        loki_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(loki_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
