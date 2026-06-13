# ADR 007: Celery i okresowa synchronizacja danych

## Status

Zaakceptowana.

## Kontekst

Aplikacja pobiera dane z kilku niezależnych usług zewnętrznych. Pobieranie dużych paczek w trakcie zwykłego requestu HTTP wydłuża odpowiedź, zwiększa ryzyko błędu 500 i uzależnia działanie interfejsu od chwilowej dostępności źródła.

## Decyzja

Synchronizacje pogody zapisanych lokalizacji, trzęsień ziemi i zdarzeń wulkanicznych wykonujemy jako zadania Celery.

Redis pełni rolę brokera i magazynu wyników zadań. Celery Beat cyklicznie dodaje zadania do kolejki, a osobny worker je wykonuje. Każde uruchomienie zapisuje stan w modelu `SyncJob`.

Publiczne endpointy zdarzeń odczytują dane z relacyjnej bazy. Przy pierwszym uruchomieniu i całkowicie pustej tabeli endpoint może wykonać synchroniczne zasilenie początkowe.

## Konsekwencje

- Frontend nie czeka na ciężką synchronizację zewnętrznych danych.
- Dane pozostają dostępne podczas krótkiej awarii źródła.
- `external_id` oraz ograniczenia unikalności zapewniają idempotentny import.
- Administrator może ręcznie uruchomić zadanie przez chroniony endpoint.
- Środowisko wymaga procesów workera i schedulera oraz działającego Redisa.
