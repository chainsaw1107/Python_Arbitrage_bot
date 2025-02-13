FROM python:3.10 as base
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
WORKDIR /app

RUN apt-get update && \
    apt-get install -y gcc libc6-dev make \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/* && \
    pip install poetry==1.3.2 --no-cache-dir 
    
RUN  python3 -m venv $VIRTUAL_ENV
COPY pyproject.toml poetry.lock ./
COPY third_party/ ./third_party/
RUN poetry install --only main --no-root

FROM python:3.10
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONPATH=.
RUN mkdir /app
WORKDIR /app
COPY --from=base $VIRTUAL_ENV $VIRTUAL_ENV

RUN python3 -m venv $VIRTUAL_ENV

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD curl --fail http://localhost:5000/ || exit 1

RUN apt-get update && \
    apt-get install -y make python3-dev --no-install-recommends

COPY olas_arbitrage/ ./olas_arbitrage/
COPY configs/ ./configs/
COPY third_party/ ./third_party/
COPY scripts/reporting.sh .
COPY README.md pyproject.toml poetry.lock ./
COPY Makefile ./
COPY error.sh ./
COPY run.sh ./

ENV PATH="$VIRTUAL_ENV/bin:$PATH"


RUN python3 -m pip install .
ENV PYTHONUNBUFFERED=TRUE

ENTRYPOINT [ "/app/run.sh"]
