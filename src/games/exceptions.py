from rest_framework.exceptions import APIException


class GameCompanyNotFound(APIException):
    status_code = 404
    default_detail = "Game not found."


class GameCompanyExists(APIException):
    status_code = 400
    default_detail = "Game name is occupied"


class GameCategoryNotFound(APIException):
    status_code = 404
    default_detail = "Game Category not found."


class GameSubCategoryNotFound(APIException):
    status_code = 404
    default_detail = "Game SubCategory not found."


class AlreadyListed(APIException):
    status_code = 400
    default_detail = "address already listed"


class NameIsOccupied(APIException):
    status_code = 400
    default_detail = "item with this name already exists in this game"
