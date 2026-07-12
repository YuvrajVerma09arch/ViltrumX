import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "viltrumx.settings.dev")

app = Celery("viltrumx")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
