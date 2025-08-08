# -------- base image ---------------------------------------------------------
FROM python:3.12

ENV PYTHONUNBUFFERED=1

ARG REACT_APP_GOOGLE_DEVELOPER_KEY
ENV REACT_APP_GOOGLE_DEVELOPER_KEY=$REACT_APP_GOOGLE_DEVELOPER_KEY


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
ARG SKIP_FRONTEND=false
ENV SKIP_FRONTEND=$SKIP_FRONTEND

RUN if [ "$SKIP_FRONTEND" != "true" ]; then \
      curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
      apt-get update && apt-get install -y nodejs && \
      rm -rf /var/lib/apt/lists/*; \
    fi

COPY ./frontend ./frontend
WORKDIR /code/frontend

RUN if [ "$SKIP_FRONTEND" != "true" ]; then \
      npm install --no-audit --no-fund --loglevel=error && \
      npm run build; \
    fi

# -------- copy built assets into Django -------------------------------------
WORKDIR /code
RUN if [ "$SKIP_FRONTEND" != "true" ]; then \
      mkdir -p agent/templates/frontend agent/static && \
      cp frontend/build/index.html agent/templates/index.html && \
      cp -r frontend/build/static/*  agent/static/; \
    fi

# -------- collectstatic ------------------------------------------------------
RUN python manage.py collectstatic --noinput

# -------- runtime ------------------------------------------------------------
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

