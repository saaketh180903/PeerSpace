FROM node:22-slim

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

CMD ["sh", "-c", "exec npm start -- --hostname 0.0.0.0 --port ${PORT:-3000}"]
