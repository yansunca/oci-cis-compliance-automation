FROM python:3.11-slim

ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=8

ARG CIS_SCRIPT_REF=bc8301a97b25dcef251e9f91042e4c8bea2c7bb6
ARG CIS_SCRIPT_SHA256=402652611432c14a48397798f9c94414b4a07ab3c5916025589fbb7bf6ae74ee

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

# Oracle's script is the same file linked by the blog, pinned to a reviewed commit and checksum.
RUN curl --fail --location --silent --show-error \
      "https://raw.githubusercontent.com/oci-landing-zones/oci-cis-landingzone-quickstart/${CIS_SCRIPT_REF}/scripts/cis_reports.py" \
      --output /app/cis_reports.py \
    && echo "${CIS_SCRIPT_SHA256}  /app/cis_reports.py" | sha256sum --check --status

COPY run_cis.py .
CMD ["python", "run_cis.py"]
