from rest_framework.exceptions import APIException


class NetworkNotFound(APIException):
    status_code = 404
    default_detail = "Network not found."
