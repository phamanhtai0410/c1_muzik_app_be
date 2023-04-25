import logging

from eth_account.messages import defunct_hash_message
from eth_utils.hexadecimal import add_0x_prefix, decode_hex, encode_hex
from ethereum.utils import ecrecover_to_pub, sha3
from rest_framework.exceptions import ValidationError
from web3 import Web3

from src.accounts.exceptions import SignatureInvalid
from src.accounts.models import AdvUser
from src.store.exceptions import TokenNotFound


def valid_metamask_message(address, signature):
    user = AdvUser.objects.filter(username__iexact=address).first()
    if not user:
        raise TokenNotFound()

    message = user.metamask_message
    if not message:
        raise TokenNotFound()
    address = Web3.toChecksumAddress(address)

    try:
        r = int(signature[0:66], 16)
        s = int(add_0x_prefix(signature[66:130]), 16)
        v = int(add_0x_prefix(signature[130:132]), 16)
        if v not in (27, 28):
            v += 27
    except ValueError:
        raise SignatureInvalid()

    message_hash = defunct_hash_message(text=message)
    pubkey = ecrecover_to_pub(decode_hex(message_hash.hex()), v, r, s)
    signer_address = encode_hex(sha3(pubkey)[-20:])

    """
    message_hash = encode_defunct(text=message)
    signer_address = Account.recover_message(message_hash, vrs=(v, r, s))
    """
    logging.info(f"matching {signer_address}, {address}")

    if signer_address.lower() != address.lower():
        raise ValidationError({"result": "Incorrect signature"}, code=400)
    user.metamask_message = None
    user.save(update_fields=("metamask_message",))
    return user
