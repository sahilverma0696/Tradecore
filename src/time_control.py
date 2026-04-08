from datetime import datetime, timedelta, timezone

class TimeChecker:
    IST_OFFSET = timedelta(hours=5, minutes=30)

    def __init__(self):
        self.ist = timezone(self.IST_OFFSET)

    def now_local(self):
        return datetime.now().strftime("%H:%M")

    def now_ist(self):
        return datetime.now(self.ist).strftime("%H:%M")

    def is_same_time(self, input_time: str):
        """Check if input_time (HH:MM) matches current IST time (rounded to minute)."""
        try:
            now_ist = datetime.now(self.ist).replace(second=0, microsecond=0)
            t = datetime.strptime(input_time, "%H:%M").time()
            input_dt = now_ist.replace(hour=t.hour, minute=t.minute)
            return now_ist == input_dt
        except ValueError:
            return False
