FROM node:20-bookworm-slim

# Install Chromium and font packages for Puppeteer
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-freefont-ttf \
    fonts-liberation \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Point Puppeteer to the system Chromium
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium \
    PORT=8001

WORKDIR /app

COPY package*.json ./
RUN npm install --omit=dev

COPY . .

# Ensure sessions directory exists
RUN mkdir -p sessions

EXPOSE 8001

CMD ["node", "server.js"]
