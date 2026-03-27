#!/bin/bash
cd /home/liuguang/tigger
set -a && source .env && set +a
exec npx @modelcontextprotocol/server-postgres "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
