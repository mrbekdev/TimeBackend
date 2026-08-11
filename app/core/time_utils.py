from datetime import datetime, date, timezone, timedelta

# Uzbekistan Timezone (UTC+5: Asia/Tashkent)
UZB_TZ = timezone(timedelta(hours=5))

def get_uzb_now() -> datetime:
    """Returns current naive datetime in Uzbekistan local time (UTC+5)."""
    return datetime.now(UZB_TZ).replace(tzinfo=None)

def get_uzb_today() -> date:
    """Returns current date in Uzbekistan local time (UTC+5)."""
    return get_uzb_now().date()
