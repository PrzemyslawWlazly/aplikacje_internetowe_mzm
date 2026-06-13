# ADR 003: PostgreSQL i relacyjny model danych

## Status

Zaakceptowano.

## Data

2026-06-12

## Decyzja

Docelową bazą aplikacji jest PostgreSQL, a schemat jest zarządzany przez Django ORM i migracje. Dane użytkownika są modelowane relacyjnie jako `User -> SavedLocation -> WeatherSnapshot`.

## Kontekst

Lokalizacja ma jednego właściciela i wiele historycznych pomiarów. Usunięcie lokalizacji powinno kaskadowo usunąć jej historię. Aplikacja musi zapewniać izolację rekordów użytkowników, unikalność współrzędnych na koncie oraz sortowanie pomiarów po czasie.

Zdarzenia sejsmiczne, wulkaniczne i logi synchronizacji również mają stabilny schemat oraz indeksy na polach używanych podczas filtrowania.

## Rozważane alternatywy

- SQLite jako jedyna baza,
- MongoDB i dokumenty zagnieżdżone w użytkowniku,
- przechowywanie historii wyłącznie w Redisie,
- zapisywanie danych w plikach JSON.

## Uzasadnienie

PostgreSQL zapewnia transakcje, ograniczenia unikalności, klucze obce, indeksy i przewidywalne zapytania czasowe. Relacja `SavedLocation -> WeatherSnapshot` naturalnie reprezentuje historię pogody bez powielania danych właściciela i współrzędnych w każdym pomiarze.

Django migrations umożliwiają odtworzenie schematu w Docker Compose i pokazują historię zmian, na przykład dodanie zachmurzenia oraz zmianę reguły unikalności lokalizacji.

SQLite pozostaje wygodnym fallbackiem podczas prostego uruchomienia lokalnego i testów, ale środowisko całej aplikacji korzysta z PostgreSQL.

## Trade-offy

- PostgreSQL wymaga osobnego kontenera i konfiguracji połączenia.
- Migracje muszą być wykonywane przed uruchomieniem aplikacji.
- Schemat relacyjny jest mniej elastyczny przy zmiennych odpowiedziach zewnętrznych API.
- Kaskadowe usuwanie upraszcza utrzymanie spójności, ale oznacza utratę historii po usunięciu lokalizacji.

## Konsekwencje

Backend nie ufa `user_id` przesyłanemu przez klienta. Właściciel jest ustawiany z JWT. Ograniczenie bazy uniemożliwia zapisanie tych samych współrzędnych dwa razy dla jednego użytkownika, ale pozwala różnym użytkownikom obserwować ten sam punkt.
