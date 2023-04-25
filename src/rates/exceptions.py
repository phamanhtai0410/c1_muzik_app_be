from rest_framework.exceptions import APIException


class CurrencyNotFound(APIException):
    status_code = 404
    default_detail = "Currency not found."
