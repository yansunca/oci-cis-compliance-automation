FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /function

COPY functions/object-storage-event-loader/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY functions/object-storage-event-loader/func.py /function/func.py

ENTRYPOINT ["/usr/local/bin/fdk", "/function/func.py", "handler"]
