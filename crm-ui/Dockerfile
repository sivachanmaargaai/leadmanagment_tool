
# Build React frontend
FROM node:22-alpine AS builder

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY . .

# Production browser traffic remains on the frontend origin; Nginx proxies /api.
ENV VITE_API_BASE_URL=""

RUN npm run build

# Serve frontend using Nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY docker/15-validate-api-upstream.sh /docker-entrypoint.d/15-validate-api-upstream.sh
RUN apk add --no-cache ca-certificates \
    && chmod +x /docker-entrypoint.d/15-validate-api-upstream.sh

# Substitute only this setting; preserve Nginx's $uri/$host variables.
ENV NGINX_ENVSUBST_FILTER="^API_UPSTREAM_HOST$"

EXPOSE 10000

CMD ["nginx", "-g", "daemon off;"]
