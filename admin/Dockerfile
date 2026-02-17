# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# Production stage - serve with nginx
FROM nginx:alpine

# Install apache2-utils for htpasswd and curl for healthcheck
RUN apk add --no-cache apache2-utils curl

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Create htpasswd file from environment variables at runtime
# Default: admin:admin (change via ADMIN_USER and ADMIN_PASSWORD env vars)
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN sed 's/\r$//' /docker-entrypoint.sh > /tmp/ep && mv /tmp/ep /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

EXPOSE 3000
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
