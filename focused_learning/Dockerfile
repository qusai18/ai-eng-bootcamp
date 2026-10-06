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
# Torch is installed by the parsers, then imported by spaCy. Leaving it
# installed makes the 512 MB instance get killed as soon as Ask starts.
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r knowledge/requirements.txt \
    && /opt/venv/bin/pip uninstall -y torch \
    && /opt/venv/bin/python -m spacy download en_core_web_sm
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
