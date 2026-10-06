FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY index.html vite.config.js ./
COPY src ./src
RUN npm run build

FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY knowledge/requirements.txt knowledge/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r knowledge/requirements.txt \
    && /opt/venv/bin/python -m spacy download en_core_web_sm \
    && /opt/venv/bin/python -c "from hyperbase import get_parser; get_parser('alphabeta', lang='en')"
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHON="/opt/venv/bin/python"
ENV NODE_ENV=production
COPY package.json package-lock.json* ./
RUN npm install --omit=dev
COPY server ./server
COPY knowledge ./knowledge
COPY --from=build /app/dist ./dist
ENV PORT=10000
EXPOSE 10000
CMD ["node", "server/start.js"]
