# PYTHON_IMAGE lets you build from a mirror if Docker Hub is unreachable, e.g.
#   $env:PYTHON_IMAGE = "mirror.gcr.io/library/python:3.12-slim"
ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
RUN useradd -r -u 10001 -M -s /usr/sbin/nologin worker
USER worker
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
