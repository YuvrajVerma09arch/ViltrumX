# Plain ASGI for now — swapped for a Channels ProtocolTypeRouter in Week 3
# when the WebSocket stream lands (see docs/BUILD-PLAN.md).
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "viltrumx.settings.dev")
application = get_asgi_application()
