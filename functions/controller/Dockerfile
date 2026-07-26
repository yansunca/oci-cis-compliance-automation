FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=8

WORKDIR /function

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --no-compile -r requirements.txt

COPY func.py /function/func.py

ENTRYPOINT ["/usr/local/bin/fdk", "/function/func.py", "handler"]
