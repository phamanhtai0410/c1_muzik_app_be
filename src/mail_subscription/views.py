from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from src.mail_subscription.models import SubscriptionUser
from src.mail_subscription.serializers import SubscriptionUserSerializer


class UserSubscriptionView(ModelViewSet):
    serializer_class = SubscriptionUserSerializer
    queryset = SubscriptionUser.objects.all()


class UserSubscriptionDeleteView(APIView):
    @swagger_auto_schema(
        operation_description="get activity",
        request_body=SubscriptionUserSerializer(),
        responses={200: "success"},
    )
    def post(self, request):
        email = self.request.data.get("email_address")
        try:
            SubscriptionUser.objects.filter(email_address__iexact=email).delete()
        except SubscriptionUser.DoesNotExist:
            pass

        return Response("success", status=status.HTTP_200_OK)
