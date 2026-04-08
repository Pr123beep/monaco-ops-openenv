FROM node:20-bookworm

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential python3 git ca-certificates \
  && npm install -g typescript \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN npm ci --no-audit --no-fund \
  && mkdir -p node_modules dist data/workspace

CMD ["bash"]
