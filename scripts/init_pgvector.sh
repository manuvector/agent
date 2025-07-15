#!/bin/sh

# Load env vars from .env (only works if there are no funny characters or spaces)
export $(grep -v '^#' .env | xargs)

echo "⚡ Creating pgvector extension if not exists in DB: $POSTGRES_DB"

docker-compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "✅ pgvector extension created (or already exists)"


docker-compose exec web python manage.py makemigrations 
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py makemigrations rag
docker-compose exec web python manage.py migrate rag

