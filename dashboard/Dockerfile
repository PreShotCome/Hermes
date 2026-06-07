# Build stage: produce the static PWA bundle.
FROM node:22-bookworm-slim AS build
WORKDIR /app
# Baked into the bundle: where the browser reaches the monitoring server.
ARG VITE_SERVER_URL=http://localhost:4000
ENV VITE_SERVER_URL=$VITE_SERVER_URL
COPY package.json ./
RUN npm install
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
COPY public ./public
RUN npm run build

# Runtime stage: serve the static files with nginx.
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
