from rest_framework.exceptions import APIException


class PackageNotFound(APIException):
    status_code = 404
    default_detail = "Package not found."


class PromotionExists(APIException):
    status_code = 400
    default_detail = "Promotion already exists"
