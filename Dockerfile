FROM python:3.11-slim

WORKDIR /app

# تثبيت المتطلبات
COPY requirements.txt .
RUN pip install --no-cache-dir websockets requests google-generativeai

# نسخ ملف البوت
COPY gen.py .

# تشغيل البوت
CMD ["python", "gen.py"]
