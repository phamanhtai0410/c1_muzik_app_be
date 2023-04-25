from rest_framework.exceptions import APIException


class RoyaltyMaxValueException(APIException):
    status_code = 400
    default_detail = "Royalty value is too high"
