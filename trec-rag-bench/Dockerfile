FROM python:3.12-slim

WORKDIR /opt/bench
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY third_party ./third_party

WORKDIR /opt/bench/app
ENV PORT=10000
EXPOSE 10000
CMD ["sh", "-c", "python -m uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
