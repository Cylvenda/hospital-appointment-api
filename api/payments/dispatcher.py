import logging
import threading

logger = logging.getLogger(__name__)


def enqueue_email_notification(*args, **kwargs):
    def _send():
        try:
            from api.notifications.task import send_notification_email
            send_notification_email(*args, **kwargs)
        except Exception:
            logger.exception("Background email notification failed")

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
