FROM python:3.12

ENV PYTHONUNBUFFERED 1

# Needed for SAML support
RUN apt-get update && \
    apt-get -y install libxml2-dev libxmlsec1-dev libxmlsec1-openssl bash bash-completion

WORKDIR /code/

COPY requirements.txt manage.py Makefile ./
RUN pip install -r requirements.txt

COPY ./agent ./agent/
COPY ./rag ./rag/

# Install Node.js and npm
RUN apt-get update && \
    apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# Build frontend
COPY ./frontend ./frontend/
WORKDIR /code/frontend
RUN npm install && npm run build

# Copy built frontend to Django templates
WORKDIR /code/

# Copy built frontend files to the correct Django folders
RUN mkdir -p agent/templates/frontend && \
    cp frontend/build/index.html agent/templates/index.html

RUN mkdir -p agent/static && \
    cp -r frontend/build/static/* agent/static/

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["make", "migrate", "runserver"]

