"""Ops alerts for provider incidents.

A single Slack-compatible webhook post (``{"text": ...}``) plus stdout
logging as the always-on fallback. Deliberately minimal: no queues, no
background workers, no retries -- an alert that cannot send must never break
or delay a student's turn beyond its short timeout.

Why this exists: the turn-level rescue in ``stream_chat`` makes provider
failures invisible by design (the student gets an answer from the fallback
model), and an unfunded or revoked key never self-heals. Without a page,
the first sign of trouble is the bill or a hard outage.
"""

from __future__ import annotations

import logging
import os
import time
from threading import Lock

import httpx

logger = logging.getLogger(__name__)

ALERT_WEBHOOK_ENV = "AI_TUTOR_ALERT_WEBHOOK_URL"
# One webhook post per kind per window; repeats inside the window only log.
# Account-state errors persist until a human acts, so per-turn posts would
# drown the one signal that matters.
ALERT_THROTTLE_SECONDS = 3600.0
_LAST_SENT: dict[str, float] = {}
_LAST_SENT_LOCK = Lock()


def send_ops_alert(kind: str, text: str) -> bool:
    """Post an ops alert, throttled per ``kind``. Returns True when posted.

    Always logs. Posts to the webhook only when ``AI_TUTOR_ALERT_WEBHOOK_URL``
    is set and the kind's throttle window has passed. Never raises; a failed
    post clears the throttle so the next occurrence retries.
    """
    logger.warning("OPS ALERT [%s]: %s", kind, text)
    url = os.environ.get(ALERT_WEBHOOK_ENV, "").strip()
    if not url:
        return False
    now = time.monotonic()
    with _LAST_SENT_LOCK:
        last = _LAST_SENT.get(kind)
        if last is not None and now - last < ALERT_THROTTLE_SECONDS:
            return False
        _LAST_SENT[kind] = now
    try:
        httpx.post(url, json={"text": f"[ai-tutor] {kind}: {text}"}, timeout=5.0)
    except Exception as exc:
        logger.warning("Ops alert webhook post failed: %s", exc)
        with _LAST_SENT_LOCK:
            _LAST_SENT.pop(kind, None)
        return False
    return True
