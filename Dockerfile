# Stage 1: Install dependencies
FROM python:latest AS build
ARG CODENAME="not_set"

ENV CODENAME=${CODENAME}
ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/${CODENAME}/venv/bin:$PATH"

WORKDIR /${CODENAME}

RUN python -m venv /${CODENAME}/venv
COPY ${CODENAME}-requirements.txt .
RUN pip install --no-cache-dir -r ${CODENAME}-requirements.txt

# Stage 2: Copy only necessary files for final image
FROM python:alpine
ARG CODENAME="not_set"

WORKDIR /${CODENAME}

ENV CODENAME=${CODENAME}
ENV PYTHONUNBUFFERED=1
ENV PATH="/venv/bin:$PATH"

COPY ${CODENAME}.py ./
COPY --from=build /${CODENAME}/venv /venv

# Stage 3: Define environment variables for use in code and execute code
ENV bucket=026090555438-stockdata
ENV rssKey=rssList.json
ENV metaKey=metadata
ENV htmlKey=htmldata
ENV headKey=tableHead.txt
ENV tableKey=tableContents.txt
ENTRYPOINT python /${CODENAME}/${CODENAME}.py
