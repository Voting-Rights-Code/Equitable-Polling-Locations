# See https://stackoverflow.com/questions/72465421/how-to-use-poetry-with-docker
FROM python:3.12.4-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/pysetup"

# to run poetry directly as soon as it's installed
ENV PATH="$POETRY_HOME/bin:$PATH"

# install poetry
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

# copy only pyproject.toml and poetry.lock file nothing else here
COPY poetry.lock pyproject.toml ./
# copy source code as own layer
RUN poetry install --no-root --no-ansi --without dev

COPY README.md ./
COPY src ./src

# this will create the folder /app/.venv and install the application
RUN poetry install --no-ansi --without dev

FROM python:3.12.4-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"


# make a user so not running as root
RUN adduser --system --no-create-home app
# copy the venv folder from builder image 
COPY --from=builder /app/.venv /app/.venv
COPY  --chown=app:app --from=builder /app/src /app/src

WORKDIR /app


USER app

ENTRYPOINT [ "/app/src/entrypoint.sh" ]