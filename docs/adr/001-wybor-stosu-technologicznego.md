# ADR 001: Wybór stosu technologicznego

## Status

Zaakceptowano.

## Data

2026-05-30

## Decyzja

W projekcie **Matka Ziemia Monitor** zostanie użyty następujący stos technologiczny:

- **Django** jako backend aplikacji,
- **Django REST Framework** jako warstwa API,
- **React + Vite** jako frontend,
- **PostgreSQL** jako relacyjna baza danych,
- **Redis** jako cache,
- **Celery** jako system zadań asynchronicznych,
- **Docker Compose** do uruchamiania całego środowiska jedną komendą.

## Kontekst

Projekt **Matka Ziemia Monitor** jest aplikacją internetową tworzoną w ramach przedmiotu *Projektowanie Aplikacji Internetowych*.

Aplikacja ma agregować i prezentować dane środowiskowe, w szczególności:

- dane pogodowe dla wybranych lokalizacji,
- dane o trzęsieniach ziemi,
- dane o aktywności wulkanicznej,
- podsumowania na dashboardzie,
- dane na interaktywnej mapie.

Projekt ma charakter edukacyjny i techniczny. Celem nie jest stworzenie komercyjnego systemu ostrzegania, lecz pokazanie poprawnej architektury aplikacji internetowej, integracji z zewnętrznymi API, cache'owania, pracy z bazą danych, konteneryzacji oraz komunikacji frontend-backend.

Aplikacja składa się z kilku części:

- backendu API,
- frontendu użytkownika,
- bazy danych,
- cache,
- w przyszłości również workera do zadań w tle.

Dlatego potrzebny jest stos technologiczny, który pozwala czytelnie rozdzielić odpowiedzialności poszczególnych elementów systemu.

## Rozważane alternatywy

### Backend

Rozważane opcje:

- Django + Django REST Framework,
- FastAPI,
- Node.js + Express,
- Node.js + NestJS.

Django zostało wybrane, ponieważ posiada dojrzały ekosystem, wbudowany system migracji, panel administracyjny, dobry model ORM oraz dobrze współpracuje z Django REST Framework.

FastAPI byłoby lżejsze i bardzo dobre do budowy API, ale wymagałoby samodzielnego dobrania większej liczby elementów, takich jak panel administracyjny, autentykacja czy struktura projektu.

Node.js z Express byłby prosty, ale wymagałby samodzielnego zaprojektowania większej części architektury. NestJS byłby bardziej uporządkowany, ale w tym projekcie Django lepiej pasuje do szybkiego stworzenia kompletnego backendu z bazą, migracjami i panelem administracyjnym.

### Frontend

Rozważane opcje:

- React + Vite,
- Vue,
- Svelte,
- klasyczne szablony Django.

React + Vite zostały wybrane, ponieważ aplikacja ma zawierać interaktywny dashboard, mapę, filtrowanie danych oraz dynamiczną komunikację z API. React dobrze nadaje się do budowy takich interfejsów.

Klasyczne szablony Django byłyby prostsze, ale gorzej pokazywałyby nowoczesną architekturę aplikacji typu frontend-backend.

### Baza danych

Rozważane opcje:

- PostgreSQL,
- SQLite,
- MySQL,
- MongoDB.

PostgreSQL zostało wybrane, ponieważ dane w projekcie mają charakter relacyjny. Użytkownik może mieć wiele zapisanych lokalizacji, lokalizacja może mieć wiele zapisanych pomiarów pogodowych, a zdarzenia środowiskowe mogą być filtrowane po czasie, typie, magnitudzie i lokalizacji.

SQLite byłoby prostsze na początku, ale gorzej pasuje do projektu uruchamianego w Docker Compose i do aplikacji, która ma pokazać bardziej realistyczną architekturę.

MongoDB mogłoby przechowywać dokumenty z API zewnętrznych, ale w tym projekcie relacje między użytkownikami, lokalizacjami i obserwacjami są wystarczająco istotne, aby wybrać bazę relacyjną.

### Cache

Rozważane opcje:

- brak cache,
- cache w pamięci procesu backendu,
- Redis.

Redis został wybrany, ponieważ aplikacja będzie korzystać z zewnętrznych API. Nie ma potrzeby pobierania tych samych danych przy każdym żądaniu użytkownika.

Redis pozwoli cache'ować między innymi:

- aktualne dane pogodowe,
- listę trzęsień ziemi z ostatnich godzin,
- dane o aktywności wulkanicznej,
- podsumowania dashboardu.

Cache w pamięci procesu backendu byłby prostszy, ale mniej stabilny i trudniejszy do kontrolowania w środowisku kontenerowym.

### Zadania asynchroniczne

Rozważane opcje:

- pobieranie danych bezpośrednio podczas requestu użytkownika,
- zewnętrzny cron,
- Celery.

Celery zostało wybrane, ponieważ pobieranie danych z API zewnętrznych może trwać dłużej lub zakończyć się błędem. Takie operacje nie powinny blokować odpowiedzi HTTP dla użytkownika.

Celery pozwoli wykonywać w tle zadania takie jak:

- cykliczne pobieranie danych pogodowych,
- cykliczne pobieranie danych sejsmicznych,
- pobieranie danych o aktywności wulkanicznej,
- czyszczenie starych danych,
- zapisywanie statusu synchronizacji.

### Uruchamianie aplikacji

Rozważane opcje:

- ręczne uruchamianie każdej usługi,
- lokalna instalacja PostgreSQL i Redis,
- Docker Compose.

Docker Compose zostało wybrane, ponieważ projekt składa się z kilku usług. Dzięki Docker Compose można uruchomić cały system jedną komendą.

## Uzasadnienie decyzji

Wybrany stos technologiczny dobrze pasuje do charakteru projektu.

Django i Django REST Framework pozwalają szybko stworzyć backend API, modele danych, migracje oraz panel administracyjny. PostgreSQL zapewnia trwałe przechowywanie danych i dobrze obsługuje relacyjny model aplikacji. React pozwala zbudować interaktywny frontend z mapą i dashboardem. Redis ma konkretne zastosowanie jako cache danych pobieranych z zewnętrznych API. Celery pozwala wykonywać synchronizację danych w tle. Docker Compose ułatwia uruchamianie całej aplikacji i spełnia wymaganie konteneryzacji.

Wybór tych technologii nie wynika wyłącznie z popularności. Każda technologia rozwiązuje konkretny problem w projekcie:

- Django porządkuje backend,
- DRF udostępnia REST API,
- React obsługuje dynamiczny interfejs,
- PostgreSQL przechowuje dane aplikacji,
- Redis ogranicza liczbę zapytań do zewnętrznych API,
- Celery obsługuje zadania w tle,
- Docker Compose upraszcza uruchomienie wielu usług.

## Konsekwencje i trade-offy

Wybrana architektura daje dobre możliwości pokazania rozwiązań technicznych, ale zwiększa złożoność projektu.

Najważniejsze konsekwencje:

- projekt będzie składał się z kilku usług,
- konieczne będzie przygotowanie plików Dockerfile,
- konieczne będzie utrzymywanie pliku docker-compose.yml,
- trzeba będzie skonfigurować połączenie Django z PostgreSQL,
- trzeba będzie skonfigurować CORS między Reactem i Django,
- trzeba będzie zaprojektować strategię cache w Redisie,
- trzeba będzie skonfigurować Celery i workera.

Alternatywnie można byłoby stworzyć prostszą aplikację wyłącznie w Django z SQLite i szablonami HTML. Taka wersja byłaby szybsza do wykonania, ale gorzej pokazywałaby architekturę nowoczesnej aplikacji internetowej oraz nie wykorzystywałaby naturalnie takich elementów jak cache, task queue i osobny frontend.

## Wynik

Przyjmujemy architekturę:

- frontend: React + Vite,
- backend: Django + Django REST Framework,
- baza danych: PostgreSQL,
- cache: Redis,
- zadania w tle: Celery,
- uruchamianie środowiska: Docker Compose.

Ta decyzja będzie podstawą dalszej konfiguracji projektu.
