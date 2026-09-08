# 平台通用容器配置（Zeabur / Sealos / Render 都能用）
# 构建时以 backend/ 为上下文
FROM python:3.12-slim

WORKDIR /app

# 先装依赖再拷代码：利用 Docker 层缓存，改代码不用重装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
