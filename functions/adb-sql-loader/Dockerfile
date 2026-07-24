FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /function

COPY functions/adb-sql-loader/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY database /function/database
COPY scanner /function/scanner
COPY scripts /function/scripts
COPY functions/adb-sql-loader/func.py /function/func.py

ENTRYPOINT ["/usr/local/bin/fdk", "/function/func.py", "handler"]
