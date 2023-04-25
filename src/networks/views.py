from rest_framework.viewsets import ModelViewSet

from src.networks.models import Network
from src.networks.serializers import NetworkSerializer


class NetworksModelView(ModelViewSet):
    """Return all supported networks."""

    serializer_class = NetworkSerializer
    queryset = Network.objects.all()
    lookup_field = "name"
