FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=10000

COPY . .

CMD ["python", "server.py"]
