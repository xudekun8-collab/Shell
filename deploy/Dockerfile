# 说明：requirements.txt 里带了 matplotlib / numpy / pillow（scripts/make_figures.py 出图用），
# 所以这个镜像体积会到 1GB 左右。不要为了瘦身删这些依赖，评估脚本还要用。
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
