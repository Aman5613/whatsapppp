# Build stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# Output: /app/dist — used by Caddy
FROM scratch AS export
COPY --from=build /app/dist /dist
