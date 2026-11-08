# 部署说明

## 本机 HTTPS 起法（已验证）

1. 生成自签证书：双击 `scripts/gen_cert.bat`（或 `D:\Git\usr\bin\openssl.exe req -x509 ...`），生成 `deploy/certs/key.pem` + `cert.pem`，有效期 825 天，SubjectAltName 含 `IP:127.0.0.1` 与 `DNS:localhost`。
2. 起 HTTPS 后端：双击 `scripts/start_https.bat`，uvicorn 起在 `0.0.0.0:8443`，带 `--ssl-keyfile` / `--ssl-certfile`。
3. 验证：`curl.exe -k https://127.0.0.1:8443/api/health` 应返回 `{"status":"ok","db":"ok"}`。

curl 不可用或不在 PATH 时，用这条不挑环境的命令代替：

```bash
backend\.venv\Scripts\python.exe -c "import httpx; print(httpx.get('https://127.0.0.1:8443/api/health', verify=False).text)"
```

HTTP 的 `backend/start_server.bat`（8000 端口）保留不动，两条路并存，答辩任选。

## 证书怎么重新生成

证书过期或丢失时，重新运行 `scripts/gen_cert.bat` 即可。`key.pem` 已加入 `.gitignore`，不会入库；`cert.pem` 是公钥可以提交。

## 小程序要改哪

- `miniprogram/utils/config.js` 的 `base_url` 当前是 `https://127.0.0.1:8443`。
- 开发者工具里必须勾选「不校验合法域名」，否则自签证书会被拦。
- 真机预览不能使用自签证书，必须换成已备案域名 + 正式证书（自签证书在真机微信里会被拦）。
- 想切回 HTTP 本地调试，把 `base_url` 改成 `http://127.0.0.1:8000` 即可。

## 备份 / 恢复

```bash
python scripts/backup_db.py      # 备份，保留最近 7 份
python scripts/verify_restore.py # 验证最新备份可恢复（导入临时库查 demo_user_1，不碰演示库）
```

详见 `docs/backup_restore.md`。

## Docker 方案（未验证）

> 本机（Windows，无 Docker/WSL）未运行验证此方案，仅作为交付的可移植部署方案。

产物：

```
deploy/Dockerfile
deploy/docker-compose.yml
deploy/nginx.conf
```

在有 Docker 的机器上验证的命令：

```bash
cd <repo>
cp deploy/.env.example deploy/.env   # 按实际填 MYSQL_ROOT_PASSWORD 等
docker compose -f deploy/docker-compose.yml up -d --build
curl -k https://127.0.0.1:8443/api/health
```

注意：

- 密钥（`AUTH_SECRET`、`WX_SECRET`、数据库密码）全部走 `env_file`，没有写进 compose / Dockerfile / nginx.conf。
- compose 读取的是 `deploy/.env`，不是 `backend/.env`；`deploy/.env` 从 `deploy/.env.example` 复制并填 `MYSQL_ROOT_PASSWORD`。
- MySQL 用命名卷 `mysql_data` 持久化，字符集 `utf8mb4`。
- `api` 通过 `depends_on: mysql: condition: service_healthy` 等 MySQL 就绪。
- nginx 对 `/api/chat/stream` 设了 `proxy_http_version 1.1` + `proxy_buffering off` + `proxy_read_timeout 300s`，否则 SSE 会被缓冲成一次性返回。

## 常见故障

- **8443 被占用**：先 `netstat -ano | findstr :8443` 找到 PID，再 `taskkill /PID <pid> /F`；或改 `start_https.bat` 里的端口。
- **证书 CN 不匹配**：确认 `gen_cert.bat` 里 `-addext "subjectAltName=IP:127.0.0.1,DNS:localhost"` 生效，访问用 `https://127.0.0.1` 或 `https://localhost`。
- **SSE 被 nginx 缓冲**：确认 `proxy_buffering off` 与 `proxy_http_version 1.1` 在 location 里，否则流式退化成一次性返回。
- **MySQL 密码错**：`backend/.env` 的 `DATABASE_URL` 里密码要与 MySQL 实际 root 密码一致。
