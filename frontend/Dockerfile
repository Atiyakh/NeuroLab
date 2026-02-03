# Build stage
FROM node:18-alpine as build

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy source
COPY . .

# Build for production
RUN npm run build

# Production stage with nginx
FROM nginx:alpine

# Copy build output
COPY --from=build /app/build /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
