# ADR 005: Redis jako cache danych zewnętrznych

## Status

Zaakceptowano.

## Data

2026-06-12

## Decyzja

Django korzysta ze współdzielonego cache Redis przez wbudowany backend `django.core.cache.backends.redis.RedisCache`. Klucze zawierają nazwę domeny danych, parametry requestu oraz wersję struktury.

## Kontekst

Open-Meteo, USGS, REST Countries i EONET są zewnętrznymi zależnościami o zmiennej dostępności oraz limitach. Wielokrotne pobranie tej samej pogody dla tych samych współrzędnych nie wnosi nowej informacji i nie powinno tworzyć duplikatów w historii.

Przyjęte TTL:

- pogoda zapisanej lokalizacji: 15 minut,
- globalna pogoda: 30 minut,
- trzęsienia ziemi: 5 minut,
- warstwa burzowa: 15 minut,
- lista stolic: 24 godziny.

## Rozważane alternatywy

- brak cache,
- lokalny `LocMemCache` procesu Django,
- cache odpowiedzi wyłącznie w przeglądarce,
- zapisywanie każdego requestu bezpośrednio w PostgreSQL.

## Uzasadnienie

Redis jest współdzielony między procesami backendu i przyszłym workerem Celery. Trafienie cache skraca odpowiedź i ogranicza ruch do API zewnętrznego. Dla zapisanej lokalizacji snapshot powstaje tylko przy braku świeżego cache, dzięki czemu historia reprezentuje pomiary rozłożone w czasie zamiast serię kliknięć użytkownika.

Wersjonowane klucze, na przykład `weather:saved-location:v2`, pozwalają zmienić format odpowiedzi bez konfliktu ze starszymi wartościami.

## Trade-offy

- Redis jest kolejną usługą wymagającą uruchomienia i monitorowania.
- Utrata cache zwiększa liczbę requestów zewnętrznych, ale nie powoduje utraty trwałej historii.
- Dane mogą być starsze maksymalnie o wartość TTL.
- Trzeba rozróżniać dane świeże, dane z cache i trwałe snapshoty PostgreSQL.

## Konsekwencje

Odpowiedź pogody zawiera flagę `cached` i `cache_ttl_seconds`. Testy używają `LocMemCache`, aby nie zależeć od zewnętrznej usługi, natomiast środowisko Docker Compose używa Redisa przez `REDIS_URL`.
