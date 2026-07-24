FROM docker.io/fnproject/python:3.11-dev AS build
WORKDIR /function
COPY requirements.txt .
RUN pip install --no-cache-dir --target /python -r requirements.txt

FROM docker.io/fnproject/python:3.11
WORKDIR /function
COPY --from=build /python /python
COPY func.py .
ENV PYTHONPATH=/python
CMD ["/python/bin/fdk", "/function/func.py", "handler"]
