FROM node:20-alpine

WORKDIR /app

# Copy package manifest + lockfile (deterministic install)
COPY package.json package-lock.json ./

# Install all deps from lockfile
RUN npm ci

# Copy application source
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
