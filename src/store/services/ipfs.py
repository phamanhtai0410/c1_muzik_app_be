import json

import ipfsclient as ipfshttpclient

from src.settings import config
from src.utilities import get_media_from_ipfs


def create_ipfs(request):
    name = request.data.get("name")
    description = request.data.get("description")
    media = request.FILES.get("media")
    cover = request.FILES.get("cover")
    attributes = request.data.get("details")
    client = ipfshttpclient.connect(config.IPFS_CLIENT, port=config.IPFS_PORT)
    res = {}
    with client as session:
        if attributes:
            attributes = json.loads(attributes)
        file_hash = session.add(media)
        ipfs_json = {
            "name": name,
            "description": description,
            "attributes": attributes,
        }
        if cover:
            cover_res = session.add(cover)
            ipfs_json["animation_url"] = get_media_from_ipfs(file_hash)
            ipfs_json["image"] = get_media_from_ipfs(cover_res)
        else:
            ipfs_json["image"] = get_media_from_ipfs(file_hash)
        # return all data for simpler token creation
        res["general"] = session.add_json(ipfs_json)
        res["image"] = ipfs_json.get("image")
        res["animation_file"] = ipfs_json.get("animation_url")
        return res


def send_to_ipfs(media):
    client = ipfshttpclient.connect(config.IPFS_CLIENT, port=config.IPFS_PORT)
    with client as session:
        file_res = session.add(media)
        return file_res


def get_ipfs(token_id, collection) -> str:
    """
    return ipfs by token
    """
    func_name = "tokenURI" if collection.is_single else "uri"
    return collection.network.contract_call(
        method_type="read",
        contract_type=f"{collection.standard.lower()}main",
        address=collection.address,
        function_name=func_name,
        input_params=(int(token_id),),
        input_type=("uint256",),
        output_types=("string",),
    )


def get_ipfs_by_hash(ipfs_hash) -> dict:
    """
    return ipfs by hash
    """
    client = ipfshttpclient.connect(config.IPFS_CLIENT, port=config.IPFS_PORT)
    with client as session:
        return session.get_json(ipfs_hash)
