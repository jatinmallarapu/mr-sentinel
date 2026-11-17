# Install the package before switching to an unprivileged runtime user.
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src/ src/
COPY config.yaml .
RUN python -m pip install --no-cache-dir .
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn","mr_sentinel.api:app","--host","0.0.0.0","--port","8000"]
