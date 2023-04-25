from drf_yasg import openapi

tx_response = openapi.Response(
    description="Return initial tx hash",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "initial_tx": openapi.Schema(type=openapi.TYPE_OBJECT),
        },
    ),
)


error_response = openapi.Response(
    description="Return json with error",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "error": openapi.Schema(type=openapi.TYPE_STRING),
        },
    ),
)


success_response = openapi.Response(
    description="Return json with success",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "success": openapi.Schema(type=openapi.TYPE_STRING),
        },
    ),
)


max_price_response = openapi.Response(
    description="Return json with success",
    schema=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "max_price": openapi.Schema(type=openapi.TYPE_STRING),
        },
    ),
)
