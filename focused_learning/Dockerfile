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
# The AlphaBeta package depends on torch. spaCy imports torch whenever it is
# installed, and that is what gets the 512 MB instance killed. Install the
# parser without that dependency and tag atoms with spaCy instead.
RUN python3 -m venv /opt/venv \
    && grep -v '^hyperbase-parser-ab' knowledge/requirements.txt > /tmp/reqs.txt \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/reqs.txt \
    && /opt/venv/bin/pip install --no-cache-dir --no-deps hyperbase-parser-ab \
    && /opt/venv/bin/pip install --no-cache-dir 'scikit-learn>=1.3' 'spacy>=3.8' \
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
