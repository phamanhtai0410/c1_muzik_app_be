from typing import Union

from src.store.exceptions import CollectionNotFound, TokenNotFound
from src.store.models import Collection, Token


def get_committed_token(token_id: int) -> "Token":
    try:
        return Token.objects.committed().get(id=token_id)
    except Token.DoesNotExist:
        raise TokenNotFound


def get_collection_by_short_url(short_url: Union[str, int]) -> "Collection":
    try:
        return Collection.objects.committed().get_by_short_url(short_url=short_url)
    except Collection.DoesNotExist:
        raise CollectionNotFound
