# Docker 部署说明

## 快速启动

### 使用 Docker Compose（推荐）

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 停止并删除所有数据
docker-compose down -v
```

启动后访问：
- 前端界面: http://localhost
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

### 单独构建

#### 后端
```bash
cd backend
docker build -t vdio-backend .
docker run -d -p 8000:8000 \
  -v $(pwd)/downloads:/app/downloads \
  --name vdio-backend \
  vdio-backend
```

#### 前端
```bash
cd frontend
docker build -t vdio-frontend .
docker run -d -p 80:80 \
  --name vdio-frontend \
  vdio-frontend
```

## 环境变量配置

后端支持的环境变量：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| DOWNLOAD_DIR | 下载文件存储目录 | /app/downloads |
| HISTORY_FILE | 历史记录文件路径 | /app/history.json |
| MAX_WORKERS | 下载线程池大小 | 4 |
| FILE_TTL | 文件保留时长（秒） | 3600 |
| CORS_ORIGINS | CORS 允许来源 | * |

示例：
```bash
docker run -d -p 8000:8000 \
  -e MAX_WORKERS=8 \
  -e FILE_TTL=7200 \
  -v $(pwd)/downloads:/app/downloads \
  vdio-backend
```

## 数据持久化

下载的文件和历史记录通过 volume 挂载持久化：

```yaml
volumes:
  - ./backend/downloads:/app/downloads    # 下载文件
  - ./backend/history.json:/app/history.json  # 历史记录
```

## 生产环境建议

1. **使用反向代理**
   - 建议在前面加一层 Nginx/Caddy 处理 SSL 证书
   - 配置速率限制防止滥用

2. **资源限制**
   ```yaml
   services:
     backend:
       deploy:
         resources:
           limits:
             cpus: '2'
             memory: 2G
   ```

3. **日志管理**
   ```yaml
   services:
     backend:
       logging:
         driver: "json-file"
         options:
           max-size: "10m"
           max-file: "3"
   ```

4. **安全加固**
   - 修改默认端口
   - 配置 CORS 白名单
   - 定期清理下载文件
   - 添加下载速率限制

## 故障排查

### 查看后端日志
```bash
docker logs -f vdio-backend
```

### 查看前端日志
```bash
docker logs -f vdio-frontend
```

### 进入容器调试
```bash
docker exec -it vdio-backend bash
```

### 清理缓存重新构建
```bash
docker-compose build --no-cache
docker-compose up -d
```
