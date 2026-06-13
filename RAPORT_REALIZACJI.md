# Raport realizacji projektu NieZmoknij

Data oceny: 13 czerwca 2026 r.

## Sposób obliczenia postępu

Ocena została wykonana względem dwóch dokumentów:

1. `PAI_Projekt_Zaliczeniowy(1).pdf` - formalne wymagania przedmiotu.
2. `Specyfikacja projektu.md` - szczegółowy plan funkcjonalny NieZmoknij.

Procent nie jest wynikiem automatycznego narzędzia. Jest oceną opartą na liście wymagań. Formalne wymagania przedmiotu otrzymały wagę 60%, a szczegółowa specyfikacja aplikacji wagę 40%. Wymagania częściowo wykonane otrzymują część punktów.

## Wymagania formalne PAI

### R1 - Backend API: zrealizowane

- Django REST Framework udostępnia REST API.
- Istnieje więcej niż wymagane minimum trzech zasobów.
- Relacje obejmują między innymi `User -> SavedLocation -> WeatherSnapshot`.
- API ma zasoby pogody, trzęsień ziemi, wulkanów, dashboardu i synchronizacji.

Ocena: 100%.

### R2 - Baza danych: zrealizowane

- Środowisko Docker używa PostgreSQL.
- Schemat jest zarządzany przez Django migrations.
- Zastosowano klucze obce, ograniczenia unikalności, walidatory i indeksy.
- Dane środowiskowe oraz logi synchronizacji są przechowywane trwale.

Ocena: 100%.

### R3 - Frontend: zrealizowane

- React i Vite tworzą aplikację SPA.
- Axios komunikuje frontend z API.
- React Leaflet pokazuje dane geograficzne.
- Recharts pokazuje historię pogody i agregacje dashboardu.

Ocena: 100%.

### R4 - Autentykacja: zrealizowane

- Logowanie używa Google OAuth 2.0 / Google Identity Services.
- Backend po weryfikacji Google wydaje własne tokeny JWT.
- Endpointy lokalizacji wymagają zalogowania.
- Endpointy synchronizacji wymagają flagi `is_staff`.

Ocena: 100%.

### R5 - Konteneryzacja: zrealizowane

`docker compose up --build` uruchamia:

- frontend,
- backend,
- PostgreSQL,
- Redis,
- Celery worker,
- Celery Beat scheduler.

Dodano healthchecki i zależności startowe kontenerów.

Ocena: 100%.

### R6 - Repozytorium: prawie zrealizowane

- Repozytorium ma historię kilku commitów, a nie jeden końcowy commit.
- Istnieje README, instrukcja uruchomienia, opis architektury i zmiennych środowiskowych.
- Istnieje osiem dokumentów ADR.
- Brakuje jeszcze commitów obejmujących dużą część najnowszych zmian oraz końcowego sprawdzenia działania workflow na GitHubie.

Ocena: 85%.

### Wynik formalnych wymagań R1-R6

Średnia: **97,5%**.

Żadne obowiązkowe wymaganie nie jest obecnie całkowicie pominięte.

## Elementy dodatkowe

Zrealizowano więcej niż wymagane trzy elementy dodatkowe:

- Redis cache z TTL i invalidacją,
- Celery jako task queue,
- 31 testów backendu,
- GitHub Actions,
- endpoint healthcheck,
- walidację danych wejściowych,
- Swagger/OpenAPI,
- komendę `seed_demo`,
- dashboard z agregacjami.

Ograniczenia:

- frontend nie ma jeszcze osobnych testów komponentów ani testów end-to-end,
- projekt nie generuje raportu procentowego pokrycia testami,
- observability nie obejmuje systemu metryk ani distributed tracing.

## Zgodność ze szczegółową specyfikacją

### Elementy zrealizowane

- publiczna mapa danych środowiskowych,
- dashboard globalny i prywatny,
- Google OAuth oraz JWT access/refresh,
- zapis i usuwanie lokalizacji użytkownika,
- wybór lokalizacji z punktów globalnej pogody,
- aktualna pogoda i historia pomiarów,
- temperatura, wilgotność, ciśnienie, wiatr i zachmurzenie,
- prawdziwe dane pogodowe Open-Meteo,
- prawdziwe dane sejsmiczne USGS,
- filtry czasu, magnitudy, głębokości i regionu,
- mapa i tabela trzęsień ziemi,
- prawdziwy katalog 1215 wulkanów holoceńskich Smithsonian GVP,
- ostatnie oraz maksymalne znane VEI,
- osobna warstwa wulkanów z ikoną `Volcano.png`,
- burze i potencjał burzowy,
- osobna warstwa cyklonów,
- panel synchronizacji dla administratora,
- logi sukcesów i błędów synchronizacji,
- preferencja dashboardu 24 godziny / 7 dni / 30 dni,
- PostgreSQL, Redis, Celery i Docker Compose,
- dokumentacja OpenAPI,
- osiem dokumentów ADR,
- scenariusz prezentacji.

### Elementy częściowe

- rejestracja jest realizowana przez pierwsze logowanie Google, a nie osobny formularz e-mail/hasło,
- nawigacja SPA działa przez stan aplikacji, ale nie wszystkie widoki mają osobne adresy URL,
- warstwy mapy są wybierane w panelu, lecz nie są nakładane jednocześnie przez klasyczny kontroler warstw Leaflet,
- dane wulkaniczne przechowują podsumowanie erupcji, a nie pełną lokalną tabelę wszystkich erupcji,
- dane demo istnieją, ale prawdziwe dane środowiskowe mają pierwszeństwo.

### Elementy pozostałe

- testy komponentów frontendu i test end-to-end głównego scenariusza,
- pełna obsługa błędów za pomocą komunikatów typu toast,
- paginacja dużych tabel API,
- finalne uporządkowanie historii commitów i uruchomienie CI na GitHubie,
- opcjonalny klasyczny formularz lokalnego konta, jeśli prowadzący uzna go za potrzebny mimo OAuth.

Ocena zgodności ze szczegółową specyfikacją: **89%**.

## Łączny postęp

Obliczenie:

```text
97,5% * 60% + 89% * 40% = 94,1%
```

Aktualny projekt jest zrealizowany w przybliżeniu w **94%**.

Najważniejsze wymagania potrzebne do zaliczenia są spełnione. Pozostałe prace dotyczą przede wszystkim jakości końcowej, testów frontendu, historii repozytorium i dopracowania prezentacji, a nie brakujących fundamentów architektury.

## Źródła danych

- [Open-Meteo](https://open-meteo.com/) - pogoda i dane używane do potencjału burzowego.
- [USGS Earthquake Hazards Program](https://earthquake.usgs.gov/fdsnws/event/1/) - trzęsienia ziemi.
- [NASA EONET](https://eonet.gsfc.nasa.gov/) - cyklony i silne systemy burzowe.
- [Smithsonian Global Volcanism Program WFS](https://volcano.si.edu/database/webservices.cfm) - katalog wulkanów i erupcji.
- [World Bank API](https://api.worldbank.org/) - stolice państw.

Smithsonian podaje obecnie 1215 wulkanów z erupcjami w holocenie. Wersja bazy widoczna 13 czerwca 2026 r. to VOTW 5.3.6 z datą 26 maja 2026 r.
