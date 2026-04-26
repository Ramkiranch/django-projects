# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Non-root user for runtime
RUN groupadd --system --gid 1000 app \
 && useradd  --system --uid 1000 --gid app --create-home --shell /bin/bash app

WORKDIR /app

# Install Python deps first so the layer is cacheable
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy the rest of the project (manage.py + bookishbailee package + apps + templates + static)
COPY . ./
RUN chmod +x /app/scripts/entrypoint.sh \
 && mkdir -p /app/staticfiles /app/media \
 && chown -R app:app /app

USER app

EXPOSE 8000
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "bookishbailee.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
