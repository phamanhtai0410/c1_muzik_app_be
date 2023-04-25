from rest_framework.exceptions import APIException


class TokenNotFound(APIException):
    status_code = 404
    default_detail = "Token not found."


class CollectionNotFound(APIException):
    status_code = 404
    default_detail = "Collection not found."


class OwnershipNotFound(APIException):
    status_code = 404
    default_detail = "Ownership not found."


class Forbidden(APIException):
    status_code = 403
    default_detail = "Operation forbidden"
