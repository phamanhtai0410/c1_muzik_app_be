import sys
import traceback

from src.bot.services import send_message


class BotMiddleware:
    """Middleware for sending errors to telegram_bot"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        _, _, stacktrace = sys.exc_info()
        message = (
            f"View error in {request.path}:\n {''.join(traceback.format_tb(stacktrace)[-2:])}"
            f"{type(exception).__name__} {exception}"
        )
        send_message(message, ["dev"])
