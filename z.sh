#!/bin/bash

# ==========================================
# PostgreSQL WAL Archive Cleanup
# ==========================================

ARCHIVE_DIR="/pgarchive"

# PostgreSQL bağlantısı
PGHOST="localhost"
PGPORT="5432"
PGUSER="postgres"
PGDATABASE="postgres"

# Replikasyon lag üzerine eklenecek güvenlik payı
SAFETY_HOURS=1

# Kaçar kaçar silinsin
BATCH_SIZE=5

LOG_FILE="/var/log/pgarchive_cleanup.log"

# Sadece normal WAL isimlerini hedefle:
# Örn: 000000010000000A000000FE
WAL_PATTERN='????????????????????????'

echo "==========================================" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') cleanup started" >> "$LOG_FILE"

# Primary'den en yüksek replay_lag değerini saniye olarak al
LAG_SECONDS=$(psql \
    -h "$PGHOST" \
    -p "$PGPORT" \
    -U "$PGUSER" \
    -d "$PGDATABASE" \
    -Atc "
SELECT COALESCE(
    CEIL(MAX(EXTRACT(EPOCH FROM replay_lag))),
    0
)
FROM pg_stat_replication
WHERE state = 'streaming';
")

# SQL/connection kontrolü
if ! [[ "$LAG_SECONDS" =~ ^[0-9]+$ ]]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: replication lag alınamadı: $LAG_SECONDS" >> "$LOG_FILE"
    exit 1
fi

# Eğer hiç standby yoksa SILME
REPLICA_COUNT=$(psql \
    -h "$PGHOST" \
    -p "$PGPORT" \
    -U "$PGUSER" \
    -d "$PGDATABASE" \
    -Atc "
SELECT count(*)
FROM pg_stat_replication
WHERE state = 'streaming';
")

if [ "$REPLICA_COUNT" -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: streaming replica bulunamadı. Silme yapılmadı." >> "$LOG_FILE"
    exit 1
fi

# Lag saniye -> saat
# 1 saniye bile varsa yukarı yuvarlar
LAG_HOURS=$(( (LAG_SECONDS + 3599) / 3600 ))

KEEP_HOURS=$((LAG_HOURS + SAFETY_HOURS))

echo "Replica count : $REPLICA_COUNT" >> "$LOG_FILE"
echo "Lag seconds   : $LAG_SECONDS" >> "$LOG_FILE"
echo "Lag hours     : $LAG_HOURS" >> "$LOG_FILE"
echo "Safety hours  : $SAFETY_HOURS" >> "$LOG_FILE"
echo "Keep hours    : $KEEP_HOURS" >> "$LOG_FILE"

# Kaç dosya silinecek önce say
DELETE_COUNT=$(
    find "$ARCHIVE_DIR" \
        -maxdepth 1 \
        -type f \
        -name "$WAL_PATTERN" \
        -mmin "+$((KEEP_HOURS * 60))" \
        -print | wc -l
)

echo "Files to delete: $DELETE_COUNT" >> "$LOG_FILE"

if [ "$DELETE_COUNT" -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') Nothing to delete." >> "$LOG_FILE"
    exit 0
fi

# 5'er 5'er sil.
# -print0 sayesinde boşluk vb. filename sorunları olmaz.
# xargs -n sayesinde ARG_MAX problemi oluşmaz.
find "$ARCHIVE_DIR" \
    -maxdepth 1 \
    -type f \
    -name "$WAL_PATTERN" \
    -mmin "+$((KEEP_HOURS * 60))" \
    -print0 |
xargs -0 -r -n "$BATCH_SIZE" rm -f --

RC=$?

if [ "$RC" -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') Cleanup completed successfully." >> "$LOG_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: cleanup failed. rc=$RC" >> "$LOG_FILE"
    exit "$RC"
fi
