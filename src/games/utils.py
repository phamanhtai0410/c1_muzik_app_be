import base64
import json
import os
import uuid

from rest_framework.exceptions import APIException

from src.store.services.ipfs import send_to_ipfs


def base64_to_ipfs(data):
    filename = str(uuid.uuid4())
    img_extensions = [
        "jpeg",
        "jpg",
        "png",
        "svg+xml",
    ]
    try:
        extension_found = False
        for ext in img_extensions:
            pattern = f"data:image/{ext};base64,"
            if data.find(pattern) >= 0:
                data = data.replace(pattern, "")
                if ext == "svg+xml":
                    ext = "svg"
                filename = filename + "." + ext
                extension_found = True
                break
        if not extension_found:
            raise Exception()

        file_path = f"{os.path.dirname(os.path.dirname(os.path.dirname(__file__)))}/static/media/{filename}"
        with open(file_path, "wb") as out_file:
            out_file.write(base64.b64decode(data))
        file = open(file_path, "rb")
        ipfs_hash = send_to_ipfs(file)
        os.remove(file_path)
        return ipfs_hash
    except Exception:
        raise APIException(detail="invalid picture")


def base64_to_json(data):
    try:
        data = data.replace("data:application/json;base64", "")
        decoded = json.loads(base64.b64decode(data))
        return decoded
    except Exception:
        raise APIException(detail="invalid json")
