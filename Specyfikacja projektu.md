# Specyfikacja projektu zaliczeniowego

## NieZmoknij - agregator danych pogodowych, sejsmicznych i wulkanicznych z cachem oraz dashboardem

## 1. Nazwa projektu

**NieZmoknij** - studencka aplikacja internetowa do agregowania, przechowywania i wizualizacji danych środowiskowych: pogody, trzęsień ziemi oraz aktywności wulkanicznej.

## 2. Charakter projektu

Projekt ma charakter edukacyjny i demonstracyjny. Celem aplikacji nie jest stworzenie komercyjnego systemu ostrzegania, lecz zbudowanie aplikacji internetowej, która pozwala pokazać świadome decyzje architektoniczne oraz praktyczne użycie różnych technologii webowych.

Aplikacja ma umożliwiać użytkownikowi obserwowanie wybranych lokalizacji oraz przeglądanie aktualnych i historycznych danych środowiskowych na mapie i dashboardzie. Szczególny nacisk zostanie położony na:

* komunikację frontend–backend,
* integrację z zewnętrznymi API,
* cache’owanie danych zewnętrznych,
* cykliczne pobieranie danych,
* przechowywanie części danych w bazie,
* wizualizację danych na mapie,
* dokumentację API,
* testy,
* konteneryzację całego systemu.

## 3. Cel aplikacji

Celem aplikacji jest zebranie w jednym miejscu podstawowych informacji o aktualnych zjawiskach naturalnych:

* aktualnej lub ostatnio pobranej pogodzie dla wybranych lokalizacji,
* trzęsieniach ziemi z ostatnich godzin lub dni,
* aktywności wulkanicznej lub zdarzeniach naturalnych powiązanych z wulkanami,
* podstawowych statystykach, np. liczba trzęsień ziemi w ostatnich 24 godzinach, największa magnituda, liczba zdarzeń według regionu.

Aplikacja ma pokazywać dane w formie:

* interaktywnej mapy,
* tabeli zdarzeń,
* prostych wykresów,
* panelu użytkownika z zapisanymi lokalizacjami.

## 4. Zakres funkcjonalny

### 4.1. Użytkownik niezalogowany

Użytkownik niezalogowany może:

* zobaczyć stronę główną aplikacji,
* zobaczyć publiczną mapę ostatnich trzęsień ziemi,
* zobaczyć podstawowy dashboard globalny,
* zarejestrować konto,
* zalogować się do aplikacji.

### 4.2. Użytkownik zalogowany

Użytkownik zalogowany może:

* dodawać obserwowane lokalizacje,
* usuwać obserwowane lokalizacje,
* przeglądać pogodę dla zapisanych lokalizacji,
* przeglądać najnowsze trzęsienia ziemi na mapie,
* filtrować trzęsienia ziemi według czasu, magnitudy i regionu,
* przeglądać zdarzenia wulkaniczne lub naturalne na osobnej warstwie mapy,
* zapisać proste preferencje dashboardu, np. domyślny zakres czasu: 24 godziny, 7 dni, 30 dni.

### 4.3. Administrator

Administrator może:

* uruchomić ręczne odświeżenie danych z API zewnętrznych,
* podejrzeć status ostatniej synchronizacji danych,
* zobaczyć logi błędów pobierania danych,
* zarządzać przykładowymi lokalizacjami widocznymi w demo.

Panel administratora może być prosty — nie musi być rozbudowany komercyjnie. Wystarczy, że pokaże różnicę uprawnień i ochronę wybranych endpointów.

## 5. Główne moduły aplikacji

## 5.1. Moduł autentykacji

Moduł odpowiada za:

* rejestrację użytkownika,
* logowanie,
* wylogowanie,
* ochronę endpointów wymagających zalogowania,
* rozróżnienie użytkownika zwykłego i administratora.

Proponowany mechanizm:

* JWT access token + refresh token
  albo
* klasyczne sesje po stronie serwera.

W projekcie studenckim JWT będzie dobrym wyborem, ponieważ łatwo pokazać komunikację między frontendem a backendem oraz ochronę endpointów API.

## 5.2. Moduł lokalizacji użytkownika

Użytkownik może zapisywać lokalizacje, które chce obserwować.

Przykład lokalizacji:

* Kraków,
* Warszawa,
* Islandia,
* Japonia,
* okolice konkretnego wulkanu,
* dowolny punkt o współrzędnych geograficznych.

Dane lokalizacji:

* nazwa,
* szerokość geograficzna,
* długość geograficzna,
* kraj lub region,
* opcjonalny opis użytkownika.

## 5.3. Moduł pogodowy

Moduł pobiera dane pogodowe dla zapisanych lokalizacji.

Minimalny zakres danych pogodowych:

* temperatura,
* wilgotność,
* ciśnienie,
* prędkość wiatru,
* opis warunków pogodowych,
* czas ostatniego pobrania danych.

Dane pogodowe powinny być cache’owane, aby aplikacja nie odpytywała zewnętrznego API przy każdym wejściu użytkownika na dashboard.

Przykładowa strategia:

* cache Redis dla danych pogodowych,
* TTL: 10–30 minut,
* po wygaśnięciu cache backend pobiera świeże dane z API,
* wybrane wyniki mogą być zapisywane w bazie jako historia pomiarów.

## 5.4. Moduł sejsmiczny

Moduł pobiera dane o trzęsieniach ziemi z zewnętrznego API.

Minimalny zakres danych:

* identyfikator zdarzenia,
* czas zdarzenia,
* magnituda,
* głębokość,
* lokalizacja tekstowa,
* współrzędne geograficzne,
* źródło danych,
* link do szczegółów zdarzenia.

Frontend powinien wyświetlać trzęsienia ziemi:

* jako punkty na mapie,
* w tabeli,
* z możliwością filtrowania według magnitudy i czasu.

Przykładowe filtry:

* ostatnia godzina,
* ostatnie 24 godziny,
* ostatnie 7 dni,
* magnituda większa niż 2.5,
* magnituda większa niż 4.5,
* tylko zdarzenia płytkie, np. głębokość poniżej 70 km.

## 5.5. Moduł aktywności wulkanicznej

Moduł pokazuje aktywność wulkaniczną lub zdarzenia naturalne związane z wulkanami.

Zakres powinien być ograniczony, aby projekt nie był zbyt duży. Wystarczy:

* pobieranie listy aktualnych lub ostatnich zdarzeń wulkanicznych,
* zapisanie wybranych zdarzeń w bazie,
* pokazanie ich na mapie jako osobna warstwa,
* pokazanie podstawowych informacji w panelu bocznym.

Dane zdarzenia wulkanicznego:

* nazwa zdarzenia,
* nazwa wulkanu lub regionu,
* współrzędne,
* data rozpoczęcia lub aktualizacji,
* źródło danych,
* opis lub krótka informacja,
* status, jeśli źródło go udostępnia.

Ten moduł powinien być traktowany jako demonstracja integracji z drugim typem danych środowiskowych, a nie jako pełny naukowy katalog wulkanów.

## 5.6. Mapa interaktywna

Mapa jest jednym z najważniejszych elementów frontendowych.

Powinna zawierać warstwy:

* trzęsienia ziemi,
* aktywność wulkaniczna,
* zapisane lokalizacje użytkownika,
* opcjonalnie prosta warstwa pogodowa dla lokalizacji użytkownika.

Funkcje mapy:

* kliknięcie punktu pokazuje szczegóły zdarzenia,
* kolor lub rozmiar punktu trzęsienia ziemi zależy od magnitudy,
* użytkownik może włączać i wyłączać warstwy,
* mapa może być ograniczona do prostych markerów — nie trzeba implementować zaawansowanych analiz GIS.

Proponowana biblioteka:

* Leaflet,
* React Leaflet.

## 5.7. Dashboard

Dashboard pokazuje podsumowanie danych.

Przykładowe elementy dashboardu:

* liczba trzęsień ziemi z ostatnich 24 godzin,
* największa magnituda z ostatnich 24 godzin,
* liczba zdarzeń według zakresu magnitudy,
* lista najnowszych zdarzeń,
* pogoda w zapisanych lokalizacjach,
* liczba aktywnych zdarzeń wulkanicznych,
* czas ostatniej synchronizacji danych.

Dashboard powinien być prosty, ale użyteczny. W projekcie ważniejsze jest pokazanie architektury niż bardzo zaawansowanych wykresów.

## 6. Wymagania minimalne projektu

## 6.1. R1 — Backend API

Aplikacja będzie posiadała backend API udostępniające zasoby powiązane relacjami.

Proponowane główne zasoby API:

1. `User`
2. `SavedLocation`
3. `WeatherSnapshot`
4. `EarthquakeEvent`
5. `VolcanicEvent`
6. `SyncJob`

Przykładowe endpointy:

```text
POST   /api/auth/register
POST   /api/auth/login
GET    /api/auth/me

GET    /api/locations
POST   /api/locations
DELETE /api/locations/{id}

GET    /api/weather/current
GET    /api/weather/history

GET    /api/earthquakes
GET    /api/earthquakes/{id}

GET    /api/volcanoes/events
GET    /api/volcanoes/events/{id}

GET    /api/dashboard/summary

POST   /api/admin/sync/earthquakes
POST   /api/admin/sync/weather
POST   /api/admin/sync/volcanoes
GET    /api/admin/sync/status
```

Relacje między zasobami:

* użytkownik ma wiele zapisanych lokalizacji,
* lokalizacja może mieć wiele zapisanych snapshotów pogodowych,
* zdarzenia sejsmiczne i wulkaniczne są pobierane z zewnętrznych źródeł,
* synchronizacje danych są zapisywane jako osobne zadania lub logi.

## 6.2. R2 — Baza danych

Aplikacja będzie używać relacyjnej bazy danych PostgreSQL.

Uzasadnienie:

* użytkownicy, lokalizacje i pomiary mają naturalne relacje,
* potrzebne są zapytania filtrujące po czasie, magnitudzie i użytkowniku,
* dane geograficzne mogą być przechowywane jako szerokość i długość geograficzna,
* PostgreSQL dobrze pasuje do aplikacji wymagającej spójności danych.

Migracje będą zarządzane narzędziem frameworka, np.:

* Django migrations,
* Prisma migrations,
* Alembic,
* Drizzle migrations.

## 6.3. R3 — Frontend

Frontend będzie aplikacją SPA.

Proponowany stack:

* React,
* Vite,
* React Router,
* Axios lub TanStack Query,
* React Leaflet,
* biblioteka wykresów, np. Recharts.

Główne widoki frontendu:

1. Strona główna
2. Logowanie i rejestracja
3. Dashboard użytkownika
4. Mapa zdarzeń
5. Lista trzęsień ziemi
6. Lista zdarzeń wulkanicznych
7. Zapisane lokalizacje
8. Panel administratora synchronizacji danych

## 6.4. R4 — Autentykacja

Aplikacja będzie posiadała mechanizm logowania.

Minimalnie:

* użytkownik niezalogowany widzi publiczne dane,
* użytkownik zalogowany może zapisywać lokalizacje,
* administrator może ręcznie uruchamiać synchronizację danych,
* wybrane endpointy są chronione.

Proponowany mechanizm:

* JWT access token + refresh token.

## 6.5. R5 — Konteneryzacja

Aplikacja będzie uruchamiana jedną komendą przy użyciu `docker-compose.yml`.

Proponowane serwisy:

```text
frontend
backend
postgres
redis
worker
scheduler
```

Minimalna wersja może zawierać:

```text
frontend
backend
postgres
redis
worker
```

Przykładowa komenda uruchomienia:

```bash
docker compose up --build
```

Po uruchomieniu:

* frontend działa na porcie 5173 lub 3000,
* backend działa na porcie 8000,
* baza PostgreSQL działa jako osobny kontener,
* Redis działa jako cache,
* worker obsługuje zadania asynchroniczne.

## 6.6. R6 — Repozytorium

Projekt będzie przechowywany w publicznym lub udostępnionym repozytorium GitHub/GitLab.

Repozytorium powinno zawierać:

* historię commitów,
* README,
* instrukcję uruchomienia,
* opis architektury,
* opis zmiennych środowiskowych,
* opis użytych technologii,
* opis ADR,
* przykładowe dane demo.

## 7. Elementy dodatkowe punktowane

Projekt powinien zawierać co najmniej 3 elementy dodatkowe. Proponowane elementy są dobrane tak, aby nie były sztucznie dodane, lecz wynikały z charakteru aplikacji.

## 7.1. Cache — Redis

Redis będzie używany do cache’owania danych z zewnętrznych API.

Cache’owane dane:

* aktualna pogoda dla lokalizacji,
* lista trzęsień ziemi z ostatnich 24 godzin,
* lista aktywnych lub ostatnich zdarzeń wulkanicznych,
* podsumowanie dashboardu.

Przykładowa strategia:

* pogoda: TTL 15 minut,
* trzęsienia ziemi: TTL 5 minut,
* zdarzenia wulkaniczne: TTL 1–6 godzin,
* dashboard: TTL 5 minut.

Uzasadnienie:

* dane zewnętrzne nie muszą być pobierane przy każdym żądaniu,
* cache zmniejsza opóźnienia,
* cache pozwala ograniczyć liczbę zapytań do zewnętrznych API,
* aplikacja może działać stabilniej przy chwilowych problemach z API zewnętrznym.

## 7.2. Task queue

Task queue będzie używana do zadań asynchronicznych.

Przykładowe zadania:

* cykliczne pobieranie danych o trzęsieniach ziemi,
* cykliczne pobieranie danych pogodowych,
* cykliczne pobieranie zdarzeń wulkanicznych,
* czyszczenie starych snapshotów pogodowych,
* zapisywanie logu synchronizacji.

Proponowane narzędzia:

* Celery + Redis dla backendu Django/FastAPI,
* BullMQ + Redis dla backendu Node.js.

Uzasadnienie:

* pobieranie danych z zewnętrznych API nie powinno blokować requestu użytkownika,
* synchronizacja danych może działać w tle,
* łatwo pokazać oddzielenie logiki HTTP od zadań asynchronicznych.

## 7.3. Testy

Projekt powinien zawierać testy jednostkowe i integracyjne.

Przykładowe testy:

* test logowania,
* test ochrony endpointów,
* test dodawania lokalizacji,
* test walidacji współrzędnych geograficznych,
* test filtrowania trzęsień ziemi po magnitudzie,
* test działania cache,
* test endpointu dashboardu.

W README należy wskazać, jak uruchomić testy.

## 7.4. CI/CD

Projekt może zawierać prosty GitHub Actions workflow.

Workflow może wykonywać:

* instalację zależności,
* uruchomienie testów backendu,
* uruchomienie testów frontendu,
* sprawdzenie formatowania lub lintingu,
* próbny build aplikacji.

Nie trzeba robić pełnego wdrożenia produkcyjnego. Wystarczy pipeline pokazujący podstawową automatyzację jakości kodu.

## 7.5. Observability

Aplikacja będzie miała podstawowe elementy obserwowalności:

* endpoint `/api/health`,
* logowanie błędów pobierania danych z API,
* zapisywanie informacji o synchronizacji,
* status ostatniej synchronizacji w panelu administratora.

Przykładowy endpoint:

```text
GET /api/health
```

Przykładowa odpowiedź:

```json
{
  "status": "ok",
  "database": "ok",
  "redis": "ok",
  "lastEarthquakeSync": "2026-05-29T18:20:00Z"
}
```

## 7.6. Walidacja danych

Dane wejściowe API będą walidowane.

Przykłady walidacji:

* szerokość geograficzna od -90 do 90,
* długość geograficzna od -180 do 180,
* magnituda jako liczba dodatnia,
* poprawny zakres dat,
* nazwa lokalizacji nie może być pusta,
* użytkownik nie może dodać dwóch identycznych lokalizacji.

## 7.7. Dokumentacja API

Backend powinien udostępniać dokumentację API.

Proponowane rozwiązania:

* Swagger/OpenAPI,
* Postman collection.

Dokumentacja powinna zawierać:

* endpointy autentykacji,
* endpointy lokalizacji,
* endpointy pogodowe,
* endpointy sejsmiczne,
* endpointy wulkaniczne,
* endpointy administracyjne.

## 7.8. Seed data

Projekt powinien mieć komendę lub skrypt tworzący dane demonstracyjne.

Przykładowe dane:

* użytkownik demo,
* administrator demo,
* kilka lokalizacji, np. Kraków, Tokio, Reykjavik, Neapol, San Francisco,
* przykładowe snapshoty pogodowe,
* przykładowe zdarzenia sejsmiczne,
* przykładowe zdarzenia wulkaniczne.

Seed data ułatwi prezentację projektu bez konieczności ręcznego klikania wszystkiego od zera.

## 8. Proponowany stack technologiczny

## 8.1. Wariant rekomendowany

```text
Frontend: React + Vite + React Router + React Leaflet + Recharts
Backend: Django + Django REST Framework
Baza danych: PostgreSQL
Cache: Redis
Task queue: Celery + Redis
Autentykacja: JWT
Dokumentacja API: Swagger/OpenAPI
Konteneryzacja: Docker Compose
CI/CD: GitHub Actions
```

## 8.2. Uzasadnienie wyboru stacku

Django REST Framework dobrze nadaje się do projektu studenckiego, ponieważ szybko pozwala stworzyć API, autentykację, migracje, panel administracyjny i dokumentację. PostgreSQL pasuje do danych relacyjnych i filtrowania zdarzeń po czasie oraz użytkowniku. Redis ma naturalne zastosowanie jako cache danych pobieranych z API zewnętrznych oraz broker dla Celery. React dobrze nadaje się do interaktywnego dashboardu i mapy.

Alternatywny stack:

```text
Frontend: React + Vite
Backend: Node.js + Express albo NestJS
Baza danych: PostgreSQL
ORM: Prisma
Cache/queue: Redis + BullMQ
```

Ten wariant również byłby poprawny, ale w przypadku projektu studenckiego Django może przyspieszyć implementację części administracyjnej, migracji i autoryzacji.

## 9. Proponowany model bazy danych

## 9.1. User

```text
id
email
password_hash
role
created_at
```

Role:

```text
USER
ADMIN
```

## 9.2. SavedLocation

```text
id
user_id
name
latitude
longitude
country
created_at
```

Relacja:

* jeden użytkownik ma wiele zapisanych lokalizacji.

## 9.3. WeatherSnapshot

```text
id
location_id
temperature
humidity
pressure
wind_speed
description
source
measured_at
created_at
```

Relacja:

* jedna lokalizacja ma wiele snapshotów pogodowych.

## 9.4. EarthquakeEvent

```text
id
external_id
title
magnitude
depth_km
latitude
longitude
place
event_time
source
detail_url
created_at
updated_at
```

## 9.5. VolcanicEvent

```text
id
external_id
title
volcano_name
latitude
longitude
region
description
event_time
source
detail_url
created_at
updated_at
```

## 9.6. SyncJob

```text
id
job_type
status
started_at
finished_at
items_fetched
error_message
```

Przykładowe typy zadań:

```text
WEATHER_SYNC
EARTHQUAKE_SYNC
VOLCANO_SYNC
```

Statusy:

```text
SUCCESS
FAILED
RUNNING
```

## 10. Proponowana struktura API

## 10.1. Autentykacja

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/refresh
GET  /api/auth/me
```

## 10.2. Lokalizacje

```text
GET    /api/locations
POST   /api/locations
GET    /api/locations/{id}
DELETE /api/locations/{id}
```

## 10.3. Pogoda

```text
GET /api/weather/current?locationId=1
GET /api/weather/history?locationId=1&days=7
```

## 10.4. Trzęsienia ziemi

```text
GET /api/earthquakes?hours=24&minMagnitude=2.5
GET /api/earthquakes/{id}
```

## 10.5. Aktywność wulkaniczna

```text
GET /api/volcanoes/events
GET /api/volcanoes/events/{id}
```

## 10.6. Dashboard

```text
GET /api/dashboard/summary
```

Przykładowa odpowiedź:

```json
{
  "earthquakesLast24h": 128,
  "maxMagnitudeLast24h": 6.1,
  "volcanicEvents": 7,
  "savedLocations": 4,
  "lastSync": {
    "earthquakes": "2026-05-29T18:20:00Z",
    "weather": "2026-05-29T18:15:00Z",
    "volcanoes": "2026-05-29T17:00:00Z"
  }
}
```

## 10.7. Panel administratora

```text
POST /api/admin/sync/weather
POST /api/admin/sync/earthquakes
POST /api/admin/sync/volcanoes
GET  /api/admin/sync/status
```

## 11. Frontend — widoki aplikacji

## 11.1. Strona główna

Zawiera:

* krótki opis aplikacji,
* link do mapy publicznej,
* przyciski logowania i rejestracji,
* informację, że projekt ma charakter edukacyjny.

## 11.2. Logowanie i rejestracja

Standardowe formularze:

* e-mail,
* hasło,
* komunikaty błędów,
* walidacja formularza.

## 11.3. Dashboard

Dashboard zawiera:

* karty ze statystykami,
* wykres liczby trzęsień ziemi według magnitudy,
* listę najnowszych zdarzeń,
* dane pogodowe dla zapisanych lokalizacji,
* status ostatniego odświeżenia danych.

## 11.4. Mapa

Mapa zawiera:

* markery trzęsień ziemi,
* markery zdarzeń wulkanicznych,
* markery zapisanych lokalizacji,
* przełączniki warstw,
* panel boczny ze szczegółami klikniętego zdarzenia.

## 11.5. Zapisane lokalizacje

Widok pozwala:

* dodać lokalizację,
* usunąć lokalizację,
* zobaczyć ostatnią pogodę,
* przejść do historii pogody.

## 11.6. Panel administratora

Widok pozwala:

* zobaczyć status synchronizacji,
* ręcznie uruchomić synchronizację,
* zobaczyć ewentualne błędy synchronizacji.

## 12. Architecture Decision Record

Projekt będzie zawierał dokument ADR. Minimalnie powinno być 5 wpisów, ale dla lepszej oceny warto przygotować 6–8 wpisów.

## 12.1. Proponowane wpisy ADR

## ADR 1 — Wybór PostgreSQL jako bazy danych

Decyzja:

* użycie PostgreSQL jako głównej bazy danych.

Kontekst:

* aplikacja przechowuje użytkowników, lokalizacje, snapshoty pogodowe i zdarzenia środowiskowe.

Alternatywy:

* MongoDB,
* SQLite,
* MySQL.

Uzasadnienie:

* dane mają relacje,
* potrzebne są migracje,
* potrzebne jest filtrowanie po czasie, użytkowniku i parametrach zdarzeń,
* PostgreSQL dobrze pasuje do tego typu aplikacji.

Trade-offy:

* konfiguracja PostgreSQL jest cięższa niż SQLite,
* dla bardzo prostego demo SQLite byłby szybszy,
* PostgreSQL wymaga osobnego kontenera.

## ADR 2 — Wybór REST API zamiast GraphQL

Decyzja:

* użycie REST API.

Kontekst:

* aplikacja ma przewidywalne zasoby: lokalizacje, pogoda, trzęsienia ziemi, zdarzenia wulkaniczne.

Alternatywy:

* GraphQL,
* tRPC.

Uzasadnienie:

* REST jest prostszy do dokumentowania przez OpenAPI,
* endpointy są czytelne,
* łatwo testować API,
* zakres projektu jest studencki i nie wymaga złożonego wybierania pól jak w GraphQL.

Trade-offy:

* REST może prowadzić do większej liczby endpointów,
* przy bardzo złożonych widokach GraphQL mógłby ograniczyć over-fetching.

## ADR 3 — Wybór Redis jako cache

Decyzja:

* użycie Redis do cache’owania danych pobieranych z zewnętrznych API.

Kontekst:

* aplikacja pobiera dane pogodowe, sejsmiczne i wulkaniczne z zewnętrznych źródeł.

Alternatywy:

* brak cache,
* cache w pamięci procesu backendu,
* zapisywanie wszystkiego tylko w bazie.

Uzasadnienie:

* Redis pozwala ograniczyć liczbę zapytań do zewnętrznych API,
* TTL pozwala kontrolować świeżość danych,
* cache poprawia szybkość działania dashboardu i mapy.

Trade-offy:

* dodatkowy serwis w docker-compose,
* konieczność zaprojektowania TTL i invalidacji,
* większa złożoność niż przy prostym odpytywaniu API bez cache.

## ADR 4 — Wybór task queue do synchronizacji danych

Decyzja:

* użycie Celery/BullMQ do asynchronicznego pobierania danych.

Kontekst:

* pobieranie danych z API zewnętrznych może być wolne lub czasowo niedostępne.

Alternatywy:

* pobieranie danych bezpośrednio w requestach użytkownika,
* cron poza aplikacją,
* ręczne pobieranie tylko z panelu administratora.

Uzasadnienie:

* zadania w tle nie blokują użytkownika,
* synchronizacja może być uruchamiana cyklicznie,
* łatwo zapisywać status synchronizacji w bazie.

Trade-offy:

* dodatkowy worker,
* dodatkowa konfiguracja,
* większa liczba kontenerów.

## ADR 5 — Wybór React + Leaflet dla mapy

Decyzja:

* użycie React oraz React Leaflet do interaktywnej mapy.

Kontekst:

* aplikacja musi wizualizować zdarzenia geograficzne.

Alternatywy:

* zwykła tabela bez mapy,
* Mapbox,
* Google Maps.

Uzasadnienie:

* Leaflet jest prosty i wystarczający dla projektu studenckiego,
* łatwo dodać markery, popupy i warstwy,
* dobrze współpracuje z Reactem.

Trade-offy:

* mniej zaawansowane możliwości niż w rozwiązaniach komercyjnych,
* przy bardzo dużej liczbie markerów może być potrzebna optymalizacja.

## ADR 6 — Wybór JWT do autentykacji

Decyzja:

* użycie JWT do logowania i ochrony endpointów.

Kontekst:

* frontend SPA komunikuje się z backendem przez API.

Alternatywy:

* sesje serwerowe,
* OAuth2,
* basic auth.

Uzasadnienie:

* JWT dobrze pasuje do SPA,
* łatwo przesyłać token w nagłówku Authorization,
* prosto rozróżnić użytkownika zalogowanego i niezalogowanego.

Trade-offy:

* trzeba poprawnie obsłużyć przechowywanie tokenów,
* odświeżanie tokenów zwiększa złożoność,
* sesje mogłyby być prostsze w klasycznej aplikacji serwerowej.

## ADR 7 — Wybór Docker Compose

Decyzja:

* użycie Docker Compose do uruchomienia całego systemu.

Kontekst:

* aplikacja składa się z kilku usług: frontend, backend, baza, Redis, worker.

Alternatywy:

* uruchamianie każdej usługi ręcznie,
* lokalna instalacja PostgreSQL i Redis,
* Kubernetes.

Uzasadnienie:

* jedna komenda uruchamia cały projekt,
* środowisko jest powtarzalne,
* łatwiej sprawdzić projekt prowadzącemu.

Trade-offy:

* trzeba przygotować Dockerfile i docker-compose.yml,
* pierwsze uruchomienie może być wolniejsze,
* debugowanie kontenerów wymaga podstawowej znajomości Dockera.

## 13. Zakres minimalny i zakres rozszerzony

## 13.1. Zakres minimalny na zaliczenie

Wersja minimalna powinna zawierać:

* rejestrację i logowanie,
* backend API,
* PostgreSQL z migracjami,
* frontend React,
* mapę z trzęsieniami ziemi,
* zapisane lokalizacje użytkownika,
* prosty dashboard,
* Redis cache,
* docker-compose,
* README,
* minimum 5 ADR,
* seed data.

## 13.2. Zakres rozszerzony na wyższą ocenę

Wersja rozszerzona może zawierać:

* task queue do synchronizacji danych,
* panel administratora synchronizacji,
* dane wulkaniczne jako osobna warstwa mapy,
* testy backendu,
* GitHub Actions,
* Swagger/OpenAPI,
* health-check endpoint,
* dashboard z wykresami,
* status ostatniego pobierania danych.

## 14. Proponowany plan implementacji

## Etap 1 — Szkielet projektu

* utworzenie repozytorium,
* przygotowanie backendu,
* przygotowanie frontendu,
* konfiguracja Docker Compose,
* podłączenie PostgreSQL.

## Etap 2 — Autentykacja

* rejestracja,
* logowanie,
* endpoint `/me`,
* ochrona endpointów.

## Etap 3 — Lokalizacje użytkownika

* model lokalizacji,
* endpointy CRUD,
* formularz dodawania lokalizacji,
* lista lokalizacji na frontendzie.

## Etap 4 — Dane sejsmiczne

* integracja z API trzęsień ziemi,
* zapis danych w bazie,
* endpoint filtrowania,
* mapa z markerami.

## Etap 5 — Cache Redis

* cache listy trzęsień ziemi,
* cache danych pogodowych,
* cache dashboardu,
* opis strategii cache w README lub ADR.

## Etap 6 — Dane pogodowe

* integracja z API pogodowym,
* widok pogody dla zapisanych lokalizacji,
* historia podstawowych snapshotów.

## Etap 7 — Dane wulkaniczne

* integracja ze źródłem danych wulkanicznych,
* osobna warstwa mapy,
* lista zdarzeń wulkanicznych.

## Etap 8 — Dashboard

* statystyki globalne,
* wykres magnitud,
* lista najnowszych zdarzeń,
* status ostatniej synchronizacji.

## Etap 9 — Task queue i synchronizacja

* worker,
* zadania pobierania danych,
* zapis logów synchronizacji,
* panel administratora.

## Etap 10 — Testy, dokumentacja i prezentacja

* testy najważniejszych endpointów,
* Swagger/OpenAPI,
* README,
* ADR,
* seed data,
* przygotowanie scenariusza demo.

## 15. Scenariusz prezentacji końcowej

Prezentacja może mieć następującą strukturę:

## 15.1. Pierwsza minuta — co robi aplikacja

Pokazanie:

* dashboardu,
* mapy trzęsień ziemi,
* warstwy aktywności wulkanicznej,
* zapisanych lokalizacji użytkownika.

## 15.2. Około 7 minut — architektura i ADR

Omówienie:

* dlaczego PostgreSQL,
* dlaczego REST,
* dlaczego Redis,
* dlaczego task queue,
* jak działa synchronizacja danych,
* jak działa docker-compose,
* jak frontend komunikuje się z backendem.

## 15.3. Ostatnie 2–3 minuty — pytania i odpowiedzi

Przykładowe pytania, na które warto być gotowym:

* Dlaczego cache jest potrzebny?
* Co się stanie, jeśli zewnętrzne API nie odpowiada?
* Dlaczego nie pobierać danych bezpośrednio z frontendu?
* Jak działa TTL w Redis?
* Dlaczego dane są częściowo zapisywane w bazie?
* Jakie są trade-offy użycia task queue?
* Czy aplikacja jest systemem ostrzegania?
* Jakie są ograniczenia dokładności danych?

## 16. Ograniczenia projektu

Aplikacja nie jest oficjalnym systemem ostrzegania przed katastrofami naturalnymi. Dane są pobierane ze źródeł zewnętrznych i służą celom edukacyjnym oraz demonstracyjnym.

Projekt nie będzie zawierał:

* zaawansowanej analizy geofizycznej,
* predykcji trzęsień ziemi,
* komercyjnego systemu alertów,
* pełnej obsługi wielu organizacji,
* skomplikowanego systemu powiadomień push.

Takie ograniczenie zakresu jest świadome, ponieważ głównym celem projektu jest pokazanie architektury aplikacji internetowej, a nie stworzenie profesjonalnego narzędzia naukowego lub komercyjnego.

## 17. Najważniejsze zalety tematu

Ten temat jest dobry na projekt z aplikacji internetowych, ponieważ pozwala pokazać wiele praktycznych zagadnień technicznych:

* integrację z zewnętrznymi API,
* projektowanie REST API,
* pracę z bazą danych,
* migracje,
* cache,
* task queue,
* mapę interaktywną,
* dashboard,
* autentykację,
* role użytkowników,
* testy,
* Docker Compose,
* dokumentację API,
* ADR z realnymi decyzjami i trade-offami.

Jednocześnie aplikacja może pozostać rozsądnie mała i wykonalna jako projekt jednoosobowy.
