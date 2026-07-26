FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# Daphne, not runserver: the Command Deck's live feed is a WebSocket, and the
# WSGI dev server can't serve the /ws/ upgrade. Daphne handles HTTP + WS on one
# port, so the whole API and the stream share this container.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "viltrumx.asgi:application"]
