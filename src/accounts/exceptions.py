from rest_framework.exceptions import APIException


class UserNotFound(APIException):
    status_code = 404
    default_detail = "User not found."


class SignatureInvalid(APIException):
    status_code = 400
    default_detail = "Invalid signature."
