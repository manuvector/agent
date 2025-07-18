#!/bin/bash
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR=~/db_backups
mkdir -p $BACKUP_DIR
docker exec -t agent_db_1 pg_dump -U postgres -d ragdb > $BACKUP_DIR/ragdb.sql

