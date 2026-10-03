FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home scheduler && mkdir -p /app/data && chown -R scheduler:scheduler /app
USER scheduler
ENV HOST=0.0.0.0 PORT=8000 DATABASE_PATH=/app/data/carbon.db
EXPOSE 8000
CMD ["python", "run.py"]
