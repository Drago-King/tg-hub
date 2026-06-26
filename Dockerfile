# Lightweight image — no Playwright/Chromium needed anymore since
# ordering uses deep links instead of browser automation.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
