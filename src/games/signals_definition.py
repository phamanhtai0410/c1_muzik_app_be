from django.dispatch import Signal

game_approved = Signal(providing_args=["instance"])
