import os
from django.core.asgi import get_asgi_application
from django.conf import settings
from channels.routing import ProtocolTypeRouter, URLRouter
from app.routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_server.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(websocket_urlpatterns),
})
