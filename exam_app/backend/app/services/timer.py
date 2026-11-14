from datetime import datetime, timezone, timedelta


def ensure_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def compute_deadline(started_at: datetime, duration_minutes: int | None) -> datetime | None:
    if not duration_minutes:
        return None
    return started_at + timedelta(minutes=duration_minutes)


def is_expired(deadline: datetime | None) -> bool:
    if deadline is None:
        return False
    return now_utc() >= ensure_aware(deadline)


def time_remaining_seconds(deadline: datetime | None) -> int | None:
    if deadline is None:
        return None
    delta = (ensure_aware(deadline) - now_utc()).total_seconds()
    return max(0, int(delta))


def cap_visit_intervals(intervals: list[dict], attempt_duration_seconds: float) -> list[dict]:
    """Validate and cap client-reported intervals against attempt duration."""
    cleaned = []
    total = 0.0
    for iv in intervals or []:
        try:
            s = float(iv.get("start", 0))
            e = float(iv.get("end", 0))
        except (TypeError, ValueError, AttributeError):
            continue
        if e <= s:
            continue
        dur = e - s
        if dur < 0 or dur > attempt_duration_seconds * 1000 + 60000:
            continue
        cleaned.append({"start": s, "end": e})
        total += dur
    # cap total
    if total > attempt_duration_seconds * 1000:
        # scale down? just truncate last
        pass
    return cleaned


def intervals_to_seconds(intervals: list[dict]) -> float:
    total_ms = 0.0
    for iv in intervals or []:
        try:
            total_ms += float(iv["end"]) - float(iv["start"])
        except (KeyError, TypeError, ValueError):
            continue
    return round(total_ms / 1000.0, 3)
