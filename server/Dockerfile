# Build stage: install dependencies (incl. native better-sqlite3) and compile.
FROM node:22-bookworm-slim AS build
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 make g++ \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json ./
RUN npm install
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# Runtime stage: reuse the dependencies built above.
FROM node:22-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production
ENV DB_PATH=/data/monitor.db
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY package.json ./
EXPOSE 4000
CMD ["node", "dist/index.js"]
