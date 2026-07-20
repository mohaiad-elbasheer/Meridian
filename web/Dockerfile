# Vite 8 needs Node >= 22; keep in sync with CI (node-version: 22).
FROM node:22-alpine AS build
WORKDIR /app
COPY web/package*.json ./
RUN npm ci
COPY web/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Without this, nginx serves its default config and every /api call 404s —
# the proxy to the api service is what makes the container functional.
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
