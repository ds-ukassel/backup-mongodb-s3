import json
from datetime import datetime, timedelta, timezone


def date_to_epoch_seconds(date) -> int:
    return int(date.timestamp())


def epoch_to_oid(epoch_seconds) -> str:
    return hex(epoch_seconds)[2:] + "0000000000000000"


def strategy_to_query(strategy, field) -> str:
    if strategy == "DAY":
        # yesterday 00:00 - today 00:00
        start_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    elif strategy == "WEEK":
        # last week Monday 00:00 - this week Monday 00:00
        start_date = (datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday() + 7)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif strategy == "MONTH":
        # last month 1st 00:00 - this month 1st 00:00
        first_of_this_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_of_last_month = first_of_this_month - timedelta(days=1)
        start_date = last_of_last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = first_of_this_month
    else:
        raise ValueError('Supported: DAY, WEEK, MONTH')

    start_epoch = date_to_epoch_seconds(start_date)
    end_epoch = date_to_epoch_seconds(end_date)

    start_oid = epoch_to_oid(start_epoch)
    end_oid = epoch_to_oid(end_epoch)

    return json.dumps({
        field: {
            "$gte": {"$oid": start_oid},
            "$lt": {"$oid": end_oid}
        }
    })


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python query-generator.py <DAY|WEEK|MONTH> <field>")
        sys.exit(1)

    strategy = sys.argv[1].upper()
    if strategy == 'FULL':
        print("")
        sys.exit(0)

    field = sys.argv[2]

    try:
        print(strategy_to_query(strategy, field))
    except ValueError as e:
        sys.exit(1)