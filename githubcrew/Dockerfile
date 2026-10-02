FROM node:22-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY index.html vite.config.js ./
COPY src ./src
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY package.json ./
RUN npm install --omit=dev
COPY server ./server
COPY --from=build /app/dist ./dist
ENV PORT=10000
EXPOSE 10000
CMD ["node", "server/index.js"]
