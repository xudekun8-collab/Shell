# 自签证书说明

本目录的 `key.pem` / `cert.pem` 由 `scripts/gen_cert.bat` 用本机 OpenSSL 生成：

```bat
scripts\gen_cert.bat
```

- `key.pem` 是私钥，已加入 `.gitignore`，不要提交。
- `cert.pem` 是自签证书，有效期 825 天，SubjectAltName 含 `IP:127.0.0.1` 与 `DNS:localhost`。
- 仅用于本地开发与答辩演示；真机预览必须换成已备案域名 + 正式证书，自签证书在真机微信里会被拦。
