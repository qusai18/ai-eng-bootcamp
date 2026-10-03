FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=10000

# The base image has Chromium. Install the matching Python package into the
# same interpreter that runs the server. Without this, the scrape dies with
# "No module named playwright" and the board stays empty.
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "server.py"]
