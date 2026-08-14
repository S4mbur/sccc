#!/bin/bash

LAG=$(psql -h HOST -p 5432 -U USER -d DB -Atc \
"SELECT EXTRACT(HOUR FROM (now() - pg_last_xact_replay_timestamp()))::int;")

HOURS=$((LAG + 1))

echo "Replication lag: $LAG saat"
echo "$HOURS saatten eski archive dosyalari silinecek."

find /pgarchive -type f -mmin +$((HOURS * 60)) -print0 | \
xargs -0 -r -n 5 rm -f
