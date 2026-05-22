FROM python:3.11-slim

WORKDIR /app

# Зависимости устанавливаем раньше копирования кода — кеш слоёв
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY anomaly_service/ ./anomaly_service/

# Непривилегированный пользователь (совпадает с run_as_user=1000 в DAG)
RUN useradd -u 1000 -m appuser
USER 1000

CMD ["python", "-m", "anomaly_service"]
