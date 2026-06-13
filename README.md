# NieZmoknij

Studencka aplikacja internetowa agregująca i wizualizująca pogodę, trzęsienia ziemi, burze, cyklony oraz katalog wulkanów.

## Architektura

- React + Vite odpowiadają za SPA, mapy Leaflet i wykresy Recharts.
- Django REST Framework udostępnia publiczne i chronione API.
- PostgreSQL przechowuje użytkowników, lokalizacje, historię pogody, zdarzenia i logi synchronizacji.
- Redis przechowuje cache odpowiedzi zewnętrznych oraz kolejkę Celery.
- Celery Worker wykonuje synchronizacje, a Celery Beat uruchamia je cyklicznie.
- Google Identity Services potwierdza tożsamość, a backend wydaje własne tokeny JWT.

Decyzje architektoniczne są opisane w katalogu `docs/adr`.









<img width="1793" height="955" alt="Screenshot from 2026-06-13 12-42-43" src="https://github.com/user-attachments/assets/2baab562-7d4d-4fb3-a44f-c3361bb8b54e" />

<img width="1793" height="955" alt="Screenshot from 2026-06-13 12-42-56" src="https://github.com/user-attachments/assets/0eb5b376-3597-46e9-807d-d562ca7e9b1d" />

<img width="1793" height="955" alt="Screenshot from 2026-06-13 12-43-05" src="https://github.com/user-attachments/assets/10989f9d-9576-4bde-8770-e98a717d4a1f" />

<img width="1793" height="731" alt="Screenshot from 2026-06-13 12-43-28" src="https://github.com/user-attachments/assets/65321354-9090-447a-ba09-06aca07d629d" />
<img width="1793" height="943" alt="Screenshot from 2026-06-13 12-43-39" src="https://github.com/user-attachments/assets/e9710df4-e51d-4a6a-9ae7-5088a6387d88" />
<img width="1793" height="943" alt="Screenshot from 2026-06-13 12-43-49" src="https://github.com/user-attachments/assets/3c66e487-eb06-4734-bd87-9db5b2d3974b" />


## Uruchomienie Docker

1. Utwórz lokalną konfigurację:

```bash
cp .env.example .env
```

2. Uzupełnij `GOOGLE_OAUTH_CLIENT_ID` w `.env`.

3. Utwórz albo uzupełnij `frontend/.env.local`:

```dotenv
VITE_API_BASE_URL=http://localhost:8001/api
VITE_GOOGLE_CLIENT_ID=identyfikator-klienta.apps.googleusercontent.com
```

4. Uruchom wszystkie serwisy:

```bash
docker compose up --build
```

Backend przed startem czeka na PostgreSQL i automatycznie wykonuje migracje.

Adresy:

- frontend: `http://localhost:5174`
- API: `http://localhost:8001/api/`
- healthcheck: `http://localhost:8001/api/health/`
- Swagger: `http://localhost:8001/api/docs/`
- Django Admin: `http://localhost:8001/admin/`

## Dane demonstracyjne

Po uruchomieniu kontenerów:

```bash
docker compose exec backend python manage.py seed_demo
```

Komenda jest idempotentna. Tworzy użytkownika `demo`, administratora `admin`, lokalizacje, historię pogody oraz przykładowe zdarzenia. Hasła można ustawić przez `DEMO_USER_PASSWORD` i `DEMO_ADMIN_PASSWORD`.

## Synchronizacja

Celery Beat uruchamia:

- trzęsienia ziemi co 5 minut,
- pogodę zapisanych lokalizacji co 15 minut,
- katalog wulkanów i erupcji raz dziennie.

Źródła danych:

- Open-Meteo: pogoda i potencjał burzowy,
- USGS: trzęsienia ziemi,
- NASA EONET: cyklony i silne systemy burzowe,
- Smithsonian Global Volcanism Program: 1215 wulkanów holoceńskich oraz historia erupcji z indeksem VEI,
- World Bank API: stolice państw używane przez globalną mapę pogody.

Globalna mapa pogody zawiera też dodatkową siatkę miast z różnych stref klimatycznych. Open-Meteo zwraca dla każdego punktu pole `is_day`, wyliczane względem lokalnego wschodu i zachodu słońca. Przy zachmurzeniu poniżej 20% aplikacja pokazuje słoneczko tylko w dzień, a uśmiechniętą gwiazdę w nocy.

`VEI` opisuje siłę konkretnej erupcji, a nie stałą cechę wulkanu. Dlatego rekord wulkanu przechowuje osobno VEI ostatniej znanej erupcji oraz najwyższe znane VEI w jego historii.

Administrator może również uruchomić zadania przez chronione endpointy:

```text
POST /api/admin/sync/earthquakes/
POST /api/admin/sync/weather/
POST /api/admin/sync/volcanoes/
GET  /api/admin/sync/status/
```

### Uprawnienia do zakładki Synchronizacja

Logowanie Google tworzy zwykłe konto bez uprawnień administracyjnych. Jest to celowe zabezpieczenie: użytkownik nie może sam nadać sobie dostępu do kolejki Celery i logów technicznych.

1. Zaloguj się do `http://localhost:8001/admin/` kontem administratora utworzonym przez `seed_demo`.
2. Otwórz sekcję `Users`.
3. Wybierz konto utworzone przez logowanie Google.
4. Zaznacz `Staff status` i zapisz formularz.
5. Wyloguj się i zaloguj ponownie w aplikacji, aby frontend pobrał aktualne pole `is_staff`.

To samo można wykonać z terminala, podstawiając adres konta Google:

```bash
docker compose exec backend python manage.py shell -c "from django.contrib.auth import get_user_model; user = get_user_model().objects.get(email='twoj-adres@gmail.com'); user.is_staff = True; user.save(update_fields=['is_staff']); print('Nadano uprawnienia:', user.email)"
```

## Uruchomienie bez Dockera

Backend może użyć SQLite jako lekkiego środowiska programistycznego, jeżeli `POSTGRES_HOST` nie jest ustawiony:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Przy uruchomieniu bez Dockera domyślny adres backendu pozostaje `http://localhost:8000`.

Frontend:

```bash
cd frontend
npm install
npm run dev -- --port 5174
```

Środowisko demonstracyjne i docelowe projektu używa PostgreSQL przez Docker Compose.

## Testy

```bash
cd backend
./.venv/bin/python manage.py test

cd ../frontend
npm run lint
npm run build
```

GitHub Actions wykonuje te same kontrole automatycznie dla pushy i pull requestów do gałęzi `main` albo `master`. Workflow znajduje się w `.github/workflows/quality.yml`.

## Zrealizowane widoki

- Dashboard z agregacjami i preferencją zakresu `24 h / 7 dni / 30 dni`.
- Mapa pogody, sejsmiki, burz, cyklonów i wszystkich wulkanów holoceńskich.
- Filtrowana tabela trzęsień ziemi.
- Prywatne zapisane lokalizacje z historią pogody.
- Panel administratora do uruchamiania synchronizacji Celery i odczytu logów `SyncJob`.

## Prezentacja

Gotowy plan demonstracji, omówienia architektury i odpowiedzi na pytania znajduje się w [`docs/SCENARIUSZ_PREZENTACJI.md`](docs/SCENARIUSZ_PREZENTACJI.md).

## Model danych

Najważniejsze relacje:

```text
User 1 --- N SavedLocation 1 --- N WeatherSnapshot
User 1 --- 1 GoogleAccount
EarthquakeEvent
VolcanicEvent
SyncJob
```

Ograniczenia bazy chronią unikalność współrzędnych użytkownika, identyfikatorów zdarzeń i pomiarów pogodowych.
