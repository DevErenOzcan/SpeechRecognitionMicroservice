# Temel imaj
FROM python:3.10-slim

# Ortam değişkenleri
ENV DJANGO_SETTINGS_MODULE django_service.settings
ENV PYTHONUNBUFFERED 1

# Sistem bağımlılıklarını yükle
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && apt-get clean

# Çalışma dizinini ayarla
WORKDIR /app

# Gereksinim dosyalarını kopyala ve kur
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Proje dosyalarını kopyala
COPY . .

# Port aç
EXPOSE 8000

# Sunucuyu başlat
CMD ["python", "manage.py", "runserver"]
