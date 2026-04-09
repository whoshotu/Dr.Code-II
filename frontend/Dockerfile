FROM node:20-alpine AS builder

WORKDIR /app

# Copy lock first for cache
COPY frontend/package*.json ./
RUN npm ci --legacy-peer-deps --no-audit --network-timeout=600000

COPY frontend/ ./
RUN npm run build

FROM nginx:alpine
LABEL org.opencontainers.image.source=https://github.com/whoshotu/Dr.Code-II
COPY --from=builder /app/build /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/templates/default.conf.template
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
