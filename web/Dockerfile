# ---- build ----------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

# Los manifiestos primero: npm ci queda en cache hasta que cambien las
# dependencias, no en cada cambio de codigo.
COPY package*.json ./
RUN npm ci

COPY . .

# Vite incrusta las variables VITE_* al compilar, asi que la URL de la API
# es argumento de construccion y no de ejecucion. Cambiarla exige reconstruir
# la imagen: es una limitacion real de las SPA estaticas, no un descuido.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---- runtime --------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
