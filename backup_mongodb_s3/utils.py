import re
import sys
import time
from typing import Callable, Any, Tuple, Type

from discord_webhook import DiscordWebhook
from pymongo import MongoClient

from backup_mongodb_s3 import config

MONGODB_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")


def is_identifier(name: str) -> bool:
    """
    Checks if a given string is a valid MongoDB identifier (e.g. for collection or column names).
    Valid identifiers start with a letter or underscore, followed by letters, digits, underscores, or hyphens.
    :param name: The string to check.
    :return: True if the string is a valid identifier, False otherwise.
    """
    return bool(MONGODB_IDENTIFIER.match(name))


def collection_exists(mongo: MongoClient, database: str, collection: str) -> bool:
    """
    Checks if a given collection exists in the MongoDB database.
    :param mongo: The MongoDB client instance.
    :param database: The name of the database.
    :param collection: The name of the collection to check.
    :return: True if the collection exists, False otherwise.
    """
    if not is_identifier(database) or not is_identifier(collection):
        raise ValueError(f"Invalid database or collection name: {database}.{collection}.")

    return collection in mongo[database].list_collection_names()

def database_exists(mongo: MongoClient, database: str) -> bool:
    """
    Checks if a given database exists in the MongoDB instance.
    :param mongo: The MongoDB client instance.
    :param database: The name of the database to check.
    :return: True if the database exists, False otherwise.
    """
    if not is_identifier(database):
        raise ValueError(f"Invalid database name: {database}.")

    return database in mongo.list_database_names()


def retry_and_wait(
        function: Callable[..., Any],
        retries: int = 3,
        delay: Callable[[int], float] = lambda attempt: (2 ** attempt),
        retry_on: Tuple[Type[Exception], ...] | Type[Exception] = (Exception,),
        *args,
        **kwargs,
) -> Any:
    """
    Retry a function call with a delay between attempts.
    :param function: The function to be called.
    :param retries: Number of retry attempts. Defaults to 3.
    :param delay: A callable that takes the attempt number and returns the delay in seconds. Defaults to exponential backoff (2^attempt seconds).
    :param retry_on: A tuple of exception types to catch and retry on. Defaults to all Exceptions.
    :param args: Positional arguments to pass to the function.
    :param kwargs: Keyword arguments to pass to the function.
    :return: The result of the function call.
    :raises: The last exception raised if all retries fail.
    """
    for attempt in range(retries):
        try:
            return function(*args, **kwargs)
        except retry_on:
            if attempt == retries - 1:
                raise
            time.sleep(delay(attempt))

    return function(*args, **kwargs)


def webhook(message: str) -> None:
    if config.DISCORD_WEBHOOK_URL:
        try:
            DiscordWebhook(url=config.DISCORD_WEBHOOK_URL, rate_limit_retry=True, content=message).execute()
        except Exception as e:
            print(f"[mongodb-backup] Failed to send Discord webhook: {e}", file=sys.stderr)
