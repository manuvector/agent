# -------- base image ---------------------------------------------------------
FROM python:3.12

ENV PYTHONUNBUFFERED=1

# -------- system deps --------------------------------------------------------
RUN apt-get update && \
    apt-get -y install \
        libxml2-dev \
        libxmlsec1-dev \
        libxmlsec1-openssl \
        bash bash-completion \
        curl && \
    rm -rf /var/lib/apt/lists/*

# -------- Python layer -------------------------------------------------------
WORKDIR /code

COPY requirements.txt manage.py Makefile ./
RUN pip install -r requirements.txt

# -------- Django apps --------------------------------------------------------
COPY ./agent ./agent
COPY ./rag   ./rag

# -------- Node / React build -------------------------------------------------
# (Done after Python deps to leverage Docker cache)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update && apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

COPY ./frontend ./frontend
WORKDIR /code/frontend
RUN npm install --no-audit --no-fund --loglevel=error && npm run build

# -------- copy built assets into Django -------------------------------------
WORKDIR /code
RUN mkdir -p agent/templates/frontend agent/static && \
    cp frontend/build/index.html agent/templates/index.html && \
    cp -r frontend/build/static/*  agent/static/

# -------- collectstatic ------------------------------------------------------
RUN python manage.py collectstatic --noinput

# -------- runtime ------------------------------------------------------------
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

