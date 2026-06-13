#!/bin/sh
# Skrypt zatrzymuje się po pierwszym błędzie polecenia.
set -e

# Jeśli skonfigurowano PostgreSQL, czekamy aż serwer zacznie przyjmować połączenia.
if [ -n "$POSTGRES_HOST" ]; then
  # Licznik ogranicza oczekiwanie do około minuty.
  attempt=1
  # Pętla wykonuje prostą próbę połączenia przez sterownik używany przez Django.
  until python -c "import psycopg2; psycopg2.connect(dbname='$POSTGRES_DB', user='$POSTGRES_USER', password='$POSTGRES_PASSWORD', host='$POSTGRES_HOST', port='$POSTGRES_PORT').close()" 2>/dev/null; do
    # Po trzydziestu próbach kończymy czytelnym błędem zamiast zapętlać kontener.
    if [ "$attempt" -ge 30 ]; then
      # Komunikat trafia do logów Docker Compose.
      echo "PostgreSQL nie jest dostępny po 30 próbach."
      # Kod różny od zera oznacza nieudany start backendu.
      exit 1
    fi
    # Informacja pokazuje postęp oczekiwania.
    echo "Oczekiwanie na PostgreSQL ($attempt/30)..."
    # Krótka przerwa daje bazie czas na inicjalizację.
    sleep 2
    # Zwiększamy licznik przed następną próbą.
    attempt=$((attempt + 1))
  done
fi

# Migracje odtwarzają aktualny schemat przed przyjęciem pierwszego requestu.
python manage.py migrate --noinput

# exec przekazuje sygnały systemowe bezpośrednio do procesu serwera Django.
exec "$@"
