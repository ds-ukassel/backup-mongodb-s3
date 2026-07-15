from datetime import datetime, timedelta, timezone
from typing import Literal, Tuple, Any

Strategy = Literal["FULL", "DAY", "WEEK", "MONTH"]
TimeStampFormat = Literal["OID", "EPOCH", "ISO"]

def date_to_epoch_seconds(date: datetime) -> int:
    return int(date.timestamp())


def epoch_to_oid(epoch_seconds: int) -> str:
    return f"{epoch_seconds:08x}0000000000000000"


def _resolve_date_range(strategy: Strategy, now: datetime = datetime.now(timezone.utc)) -> Tuple[datetime, datetime]:
    """
    Resolves the start and end datetime for a given strategy (DAY, WEEK, MONTH) based on the current datetime.
    :param strategy: The strategy to resolve the date range for. Can be "DAY", "WEEK", or "MONTH".
    :param now: The current datetime. Defaults to the current UTC time.
    :return: A tuple containing the start and end datetime for the given strategy based on the current datetime.
    """
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    match strategy:

        case "DAY":
            return today_midnight - timedelta(days=1), today_midnight

        case "WEEK":
            monday = today_midnight - timedelta(days=today_midnight.weekday())
            last_monday = monday - timedelta(days=7)
            return last_monday, monday

        case "MONTH":
            first_this_month = today_midnight.replace(day=1)
            last_prev_month = first_this_month - timedelta(days=1)
            start = last_prev_month.replace(day=1)
            return start, first_this_month

    raise ValueError(f"Unsupported strategy: {strategy}.")


def _resolve_bounds(ts_format: TimeStampFormat, start: datetime, end: datetime) -> dict[str, dict[str, str] | datetime | int]:
    """
    Resolves the bounds ($gte, $lt) for a given timestamp format (OID, EPOCH, ISO) based on the start and end datetime.
    :param ts_format: The timestamp format to resolve the bounds for. Can be "OID", "EPOCH", or "ISO".
    :param start: The start datetime.
    :param end: The end datetime.
    :return: A dictionary containing the resolved bounds ($gte, $lt) for the given timestamp format based on the start and end datetime.
    """
    start_epoch = date_to_epoch_seconds(start)
    end_epoch = date_to_epoch_seconds(end)

    match ts_format:
        case "OID":
            return {
                "$gte": {"$oid": epoch_to_oid(start_epoch)},
                "$lt": {"$oid": epoch_to_oid(end_epoch)},
            }
        case "EPOCH":
            return {
                "$gte": start_epoch,
                "$lt": end_epoch,
            }
        case "ISO":
            return {
                "$gte": start,
                "$lt": end,
            }

    raise ValueError(f"Unsupported timestamp format: {ts_format}.")


def strategy_to_query(strategy: Strategy, database: str, collection: str, ts_column: str, ts_format: TimeStampFormat) -> Tuple[str, dict[str, Any]]:
    now = datetime.now(timezone.utc)

    if strategy == "FULL":
        backup_date = now
    else:
        backup_date, _ = _resolve_date_range(strategy, now)

    match strategy:
        case "FULL":
            backup_timestamp = backup_date.strftime("%Y-%m-%d_%H-%M-%S")
        case "MONTH":
            backup_timestamp = backup_date.strftime("%Y-%m")
        case "WEEK" | "DAY":
            backup_timestamp = backup_date.strftime("%Y-%m-%d")
        case _:
            raise ValueError(f"Unsupported strategy: {strategy}.")

    if strategy != "FULL":
        start_datetime, end_datetime = _resolve_date_range(strategy, now)
        bounds = {ts_column: _resolve_bounds(ts_format, start_datetime, end_datetime)}
    else:
        bounds = {}

    return f"{database}{'_' if collection else ''}{collection}_{strategy}_{backup_timestamp}.bson.gz", bounds
