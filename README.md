cat > README.md <<'EOF'
# Matka Ziemia Monitor

Aplikacja internetowa do agregowania, cache'owania i wizualizacji danych pogodowych, sejsmicznych oraz wulkanicznych.

Projekt realizowany w ramach przedmiotu **Projektowanie Aplikacji Internetowych**.

## Planowany stack technologiczny

- Frontend: React + Vite
- Backend: Django + Django REST Framework
- Baza danych: PostgreSQL
- Cache: Redis
- Task queue: Celery
- Konteneryzacja: Docker Compose

## Główne funkcje

- logowanie i rejestracja użytkowników,
- zapisywanie obserwowanych lokalizacji,
- pobieranie danych pogodowych,
- pobieranie danych o trzęsieniach ziemi,
- pobieranie danych o aktywności wulkanicznej,
- interaktywna mapa,
- dashboard z podsumowaniem danych,
- cache danych z zewnętrznych API,
- cykliczna synchronizacja danych.

## Uruchomienie projektu

```bash
docker compose up --build
