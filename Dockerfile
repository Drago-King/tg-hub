# Using Playwright's official image: it already bundles Chromium +
# every system dependency it needs (fonts, libs, etc). This sidesteps
# the apt-get dependency issues that come from installing Playwright
# manually on a generic base image.
FROM mcr.microsoft.com/playwright/python:v1.48.0-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Browser binaries are already in the base image, but this is a safe
# no-op confirmation step in case the base image version drifts.
RUN python -m playwright install chromium

COPY . .

# Railway sets PORT but this bot doesn't serve HTTP — it long-polls
# Telegram. No EXPOSE/port binding needed for a polling-based bot.

CMD ["python", "main.py"]
