import json

import requests

from src.settings import config


def check_captcha(response):
    data = {"secret": config.CAPTCHA_SECRET, "response": response}
    response = requests.post(config.CAPTCHA_URL, data=data)
    answer = json.loads(response.text)
    return answer["success"]
