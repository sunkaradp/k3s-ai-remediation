FROM python:3.12-slim

WORKDIR /app

# Apply current Debian security and package updates at image build time.
# This keeps the runtime image on patched OS packages instead of relying
# only on the packages bundled in the upstream Python base image.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --uid 10001 --no-create-home app

COPY pyproject.toml .
COPY app ./app
RUN pip install --no-cache-dir .

USER 10001
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
