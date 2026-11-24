FROM node:22-bookworm-slim AS build
WORKDIR /src
COPY package.json ./
RUN npm install
COPY . .
ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine
# Pick up patched Alpine packages published after the base tag was cut. The
# container scan remains fail-closed for anything Alpine has not fixed yet.
RUN apk upgrade --no-cache
# Explicit non-root UID (the base image already uses 101). Declared so
# container scanners do not flag a missing USER instruction.
USER 101
COPY nginx-limits.conf /etc/nginx/conf.d/00-ingress-limits.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 8080
