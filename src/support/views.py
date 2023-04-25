from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from src.support.models import Config
from src.support.serializers import ConfigSerializer


@swagger_auto_schema(
    method="get",
    operation_description="Get config data",
    responses={200: ConfigSerializer},
)
@api_view(http_method_names=["GET"])
def get_config_data(_):
    return Response(
        ConfigSerializer(Config.object()).data,
        status=status.HTTP_200_OK,
    )
