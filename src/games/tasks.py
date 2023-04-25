import json
import logging

import requests
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from celery import shared_task
from src.decorators import ignore_duplicates
from src.games.utils import base64_to_ipfs, base64_to_json
from src.networks.models import Network
from src.store.models import Collection, Status, Token
from src.store.services.ipfs import get_ipfs
from src.support.models import EmailConfig, EmailTemplate
from src.support.tasks import send_email_notification
from src.utilities import RedisClient, get_media_from_ipfs

from .import_limits import get_import_requests_exceeded, increment_import_requests
from .models import GameCategory, GameCompany, GameSubCategory

logger = logging.getLogger("celery")


@shared_task(name="parse_metadata_starter")
@ignore_duplicates
def parse_metadata_starter():
    """
    Periodically send tasks to parse metadata
    """
    tokens = Token.objects.filter(status=Status.IMPORTING).exclude(image__isnull=False)
    networks = Network.objects.all()
    for network in networks:
        if get_import_requests_exceeded(network):
            continue
        for token in tokens.filter(collection__network=network):
            process_parse_metadata.apply_async(args=(token.id,), priority=5)


@shared_task(name="process_parse_metadata")
@ignore_duplicates
def process_parse_metadata(token_id: int) -> None:
    """
    Parses token metadata and saves in DB (if not duplicate)
    """

    token = Token.objects.get(id=token_id)
    if token.image:
        return
    metadata_value = get_ipfs(token.internal_id, token.collection)
    increment_import_requests(token.collection.network)

    print(f"metadata_value for token {token} is {metadata_value}")
    if metadata_value.startswith("ipfs://"):
        metadata_value = metadata_value.replace("ipfs://", "https://ipfs.io/ipfs/")

    url_validator_validate = URLValidator()
    try:
        url_validator_validate(metadata_value)
        res = requests.get(metadata_value)
        if res.status_code != 200:
            raise Exception(f"cannot fetch metadata for uri {metadata_value}")
        metadata_json = res.json()

    except ValidationError:
        if metadata_value.startswith("data"):
            metadata_json = base64_to_json(metadata_value)
        else:
            metadata_json = json.loads(metadata_value)

    name = metadata_json.get("name")
    if name:
        if str(name).lstrip("#").isdigit():
            name = token.collection.name + str(name)
        token.name = name
    if not str(token.internal_id) in token.name and Token.objects.filter(
        collection__network=token.collection.network, name=token.name
    ):
        token.name += f" {token.internal_id}"
    image_file = metadata_json.get("image")
    if image_file.startswith("data"):
        image_file = get_media_from_ipfs(base64_to_ipfs(image_file))
    token.image = image_file.replace("ipfs://", "https://ipfs.io/ipfs/")
    animation_file = metadata_json.get("animation_url")
    if animation_file:
        token.animation_file = animation_file.replace(
            "ipfs://", "https://ipfs.io/ipfs/"
        )
    token.description = metadata_json.get("description")

    attributes = metadata_json.get("attributes")
    if attributes:
        try:
            token._parse_and_save_details(attributes)
        except Exception:
            pass

    token.status = Status.COMMITTED
    token.save()


@shared_task(name="validate_game")
def validate_game(instance_id):
    game = GameCompany.objects.get(id=instance_id)
    process_validate_game(game)


@shared_task(name="validate_game_category")
def validate_game_category(instance_id):
    game_category = GameCategory.objects.get(id=instance_id)
    process_validate_game(game_category.game)


@shared_task(name="validate_game_subcategory")
def validate_game_subcategory(instance_id):
    game_subcategory = GameSubCategory.objects.get(id=instance_id)
    process_validate_game(game_subcategory.category.game)


@shared_task(name="validate_game_collection")
def validate_game_collection(instance_id):
    collection = Collection.objects.get(id=instance_id)
    process_validate_game(collection.game_subcategory.category.game)


def process_validate_game(game_instance):
    game_instance.validate_contracts()
    game_instance.parse_collections()
    game_instance.delete_empty_nested_models()
    game_instance.set_deploy_blocks()
    game_instance.refresh_from_db()
    if game_instance.validating_result == "valid":
        key = EmailTemplate.construct_email(
            "NEW_EVENT", game_instance, EmailConfig.get_admin_receiver()
        )
        if key:
            send_email_notification.apply_async(args=(key,), priority=3)


@shared_task(name="clear_import_requests")
def clear_import_requests():
    redis = RedisClient()
    redis_key_filter = "import_requests__*"
    keys = redis.connection.keys(redis_key_filter)
    for key in keys:
        redis.connection.delete(key)
