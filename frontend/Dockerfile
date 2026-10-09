FROM node:22-slim

ENV NEXT_TELEMETRY_DISABLED=1 \
    PORT=3010 \
    NODE_OPTIONS="--dns-result-order=ipv4first"

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

EXPOSE 3010

CMD ["sh", "-c", "exec npx next start --hostname 0.0.0.0 --port ${PORT:-3010}"]
