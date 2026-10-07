FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt -r detector/requirements.txt
ENV FIRESTORE=1 EE_USE_ADC=1 PYTHONUNBUFFERED=1
CMD exec gunicorn -b :$PORT -w 1 --threads 4 --timeout 300 servidor:app
