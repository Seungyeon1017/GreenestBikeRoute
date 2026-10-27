#!/bin/sh

find /app/.next \( -type d -name .git -prune \) -o -type f -print0 | xargs -0 sed -i "s#NEXT_PUBLIC_DIRECTUS_URL#$NEXT_PUBLIC_DIRECTUS_URL#g"
find /app/.next \( -type d -name .git -prune \) -o -type f -print0 | xargs -0 sed -i "s#ECOCOUNTER_API_TOKEN#$ECOCOUNTER_API_TOKEN#g"

if [ "$MIGRATE_DATABASE" = true ]
then
  echo "Running database migrations"
  npx --yes prisma migrate deploy
else
  echo 'No Database migrations will be applied.'
  echo 'If there are missing Database migrations set environment variable MIGRATE_DATABASE to true'
fi

echo "Starting App"
exec "$@"