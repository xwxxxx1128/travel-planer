# 阶段一：构建前端静态资源
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
# Vite 在 build 时把环境变量 bake 进产物；地图等公用变量在 .env.production 中提供
ARG VITE_AMAP_JS_API_KEY
ENV VITE_AMAP_JS_API_KEY=$VITE_AMAP_JS_API_KEY
RUN npm run build

# 阶段二：用 nginx 提供静态文件 + 反向代理后端（支持 SSE 流式）
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
