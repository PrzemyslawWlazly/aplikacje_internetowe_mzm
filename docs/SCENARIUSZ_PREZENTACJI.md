# Scenariusz prezentacji NieZmoknij

Dokument wymaga prezentacji trwającej **10-11 minut**: około 1 minuty opisu aplikacji, około 7 minut architektury i ADR oraz 2-3 minut na pytania. Poniższy scenariusz obejmuje około **7 minut przygotowanej wypowiedzi i demo**, pozostawiając czas na krótkie otwarcie oraz Q&A.

## Przygotowanie przed prezentacją

1. Uruchom aplikację: `docker compose up --build`.
2. Przygotuj dane: `docker compose exec backend python manage.py seed_demo`.
3. Otwórz frontend: `http://localhost:5174`.
4. Otwórz Swagger: `http://localhost:8001/api/docs/`.
5. Przygotuj konto Google zwykłego użytkownika oraz konto `staff` do pokazania synchronizacji.
6. Sprawdź wcześniej GitHub Actions i ostatni zielony przebieg pipeline.

## 0:00-0:45 - Problem i cel

Powiedz:

> NieZmoknij agreguje pogodę, trzęsienia ziemi, burze, cyklony i zdarzenia wulkaniczne. Projekt nie jest systemem ostrzegania. Jego celem jest pokazanie kompletnej architektury aplikacji internetowej: API, relacyjnej bazy, cache, zadań w tle, autoryzacji i interaktywnego frontendu.

Pokaż przez kilka sekund mapę pogodową i Dashboard.

## 0:45-2:10 - Demo najważniejszych funkcji

1. Na Dashboardzie pokaż liczbę trzęsień, największą magnitudę, wykres i status synchronizacji.
2. Zmień preferencję z `24 h` na `7 dni`. Wyjaśnij, że wartość zapisuje się w PostgreSQL dla danego użytkownika.
3. Otwórz zakładkę `Zdarzenia`, ustaw `M 4.5+` i głębokość do `70 km`.
4. Kliknij `Mapa` przy jednym rekordzie. Pokaż, że filtrowany zestaw trafia na warstwę sejsmiczną.
5. Przełącz warstwę na `Wulkany` i wybierz zdarzenie z listy.

## 2:10-3:10 - Model danych i API

Powiedz:

> Backend to Django REST Framework. PostgreSQL przechowuje użytkowników, preferencje, lokalizacje, historię pogody, zdarzenia sejsmiczne, wulkaniczne i logi synchronizacji. Relacja User 1:1 UserPreference zapisuje zakres Dashboardu, a User 1:N SavedLocation 1:N WeatherSnapshot pokazuje właściwe relacje domenowe.

Pokaż Swagger i endpointy:

- `GET /api/dashboard/summary/`,
- `GET /api/earthquakes/`,
- `GET /api/volcanoes/events/`,
- `PATCH /api/auth/preferences/`,
- `POST /api/admin/sync/{type}/`.

## 3:10-4:10 - Cache i zadania asynchroniczne

Powiedz:

> Redis ma dwie konkretne role. Jest cachem danych pogodowych i Dashboardu oraz brokerem Celery. Dashboard ma TTL pięć minut i osobne klucze dla 24 godzin, 7 dni i 30 dni. Zmiana danych unieważnia właściwy cache. Celery Worker pobiera dane poza requestem HTTP, a Celery Beat uruchamia zadania cyklicznie.

Zaloguj konto administratora i pokaż zakładkę `Synchronizacja`:

1. uruchom synchronizację wulkanów,
2. pokaż odpowiedź o dodaniu do kolejki,
3. odśwież logi i wskaż rekord `SyncJob`.

## 4:10-5:30 - Najważniejsze ADR

Omów krótko cztery decyzje:

1. **Django REST Framework zamiast samego Django lub FastAPI**
   Zysk: ORM, migracje, admin i spójna walidacja. Koszt: cięższy framework.

2. **PostgreSQL zamiast MongoDB i SQLite**
   Zysk: relacje, ograniczenia, indeksy i filtrowanie. Koszt: osobna usługa i konfiguracja.

3. **Google Identity + lokalne JWT**
   Google potwierdza tożsamość, ale backend wydaje własne tokeny do ochrony API. Koszt: konfiguracja originów OAuth i mechanizm odświeżania tokenu.

4. **Redis + Celery**
   Cache ogranicza requesty zewnętrzne, a kolejka nie blokuje użytkownika. Koszt: dwa dodatkowe procesy i potrzeba obserwowalności.

Wspomnij, że repozytorium zawiera siedem ADR, czyli więcej niż wymagane minimum pięciu.

## 5:30-6:20 - Konteneryzacja i jakość

Powiedz:

> Docker Compose uruchamia frontend, backend, PostgreSQL, Redis, worker i scheduler. Healthcheck backendu sprawdza bazę i Redis. Testy obejmują autoryzację, izolację danych użytkowników, cache, filtry, synchronizację i Dashboard.

Pokaż:

- `docker compose ps`,
- zielony workflow GitHub Actions,
- komendy `python manage.py test`, `npm run lint`, `npm run build`.

## 6:20-7:00 - Podsumowanie i świadome ograniczenia

Powiedz:

> Projekt świadomie nie jest naukowym katalogiem ani systemem alarmowym. Zewnętrzne źródła mogą być chwilowo niedostępne, dlatego stosuję cache, fallback i trwałą bazę. Najważniejszym rezultatem jest spójność architektury: każdy dodatkowy komponent ma konkretną rolę i jest faktycznie używany.

Zakończ zdaniem:

> Aplikacja spełnia R1-R6 i pokazuje dodatkowo cache, task queue, testy, CI, observability, Swagger, seed data oraz warstwę analityczną.

## Prawdopodobne pytania

### Dlaczego nie pobierasz danych bezpośrednio z API w React?

Backend ukrywa szczegóły źródeł, waliduje dane, ogranicza liczbę requestów przez Redis i utrwala wybrane rekordy. Frontend otrzymuje stabilny kontrakt niezależny od zmian API zewnętrznego.

### Dlaczego Redis, skoro dane są w PostgreSQL?

PostgreSQL jest źródłem trwałych danych. Redis przechowuje krótkotrwałe, często odczytywane wyniki i pełni rolę brokera Celery. Te role nie zastępują się.

### Co się stanie przy awarii API zewnętrznego?

Synchronizacja zapisze stan `FAILED` i treść błędu w `SyncJob`. Dla pogody i burz aplikacja może użyć ostatniej dobrej wartości cache. Trwałe zdarzenia pozostają dostępne w PostgreSQL.

### Jak zapewniona jest separacja danych użytkowników?

Endpointy lokalizacji filtrują queryset przez `request.user`, a preferencje mają relację OneToOne. Testy sprawdzają, że użytkownik nie odczyta ani nie usunie cudzego zasobu.

### Dlaczego aplikacja ma tyle usług?

Każda ma osobną odpowiedzialność: PostgreSQL zapewnia persystencję, Redis cache i broker, worker wykonuje zadania, scheduler je planuje, Django udostępnia API, a React interfejs. Koszt złożoności jest jawnie opisany w ADR.
