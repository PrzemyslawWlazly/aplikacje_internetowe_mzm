from datetime import timedelta  # Timedelta pozwala przygotować zdarzenia wewnątrz i poza zakresem Dashboardu.
from urllib.error import HTTPError  # HTTPError pozwala zasymulować niedostępność zewnętrznego źródła.
from unittest.mock import patch  # Mock odcina testy od prawdziwych API zewnętrznych.

from django.contrib.auth import get_user_model  # Funkcja zwraca aktywny model użytkownika projektu.
from django.core.cache import cache  # Cache czyścimy między testami, aby zachować ich niezależność.
from django.test import override_settings  # Dekorator zastępuje Redis szybkim cache w pamięci testu.
from django.utils import timezone  # Czas świadomy strefowo jest potrzebny rekordom zdarzeń i synchronizacji.
from rest_framework import status  # Nazwane kody HTTP poprawiają czytelność asercji.
from rest_framework.test import APITestCase  # Klasa udostępnia klienta API i testową bazę danych.

from .models import (  # Modele pozwalają sprawdzić trwały zapis wszystkich synchronizowanych danych.
    EarthquakeEvent,
    SavedLocation,
    SyncJob,
    VolcanicEvent,
    WeatherSnapshot,
)
from .sync_services import synchronize_earthquakes, synchronize_volcanic_events  # Testujemy właściwe usługi importujące.
from .views import (  # Importujemy helpery i klucze potrzebne do testów regresji zewnętrznych źródeł.
    CAPITAL_POINTS_CACHE_KEY,
    CAPITAL_POINTS_FALLBACK_KEY,
    CYCLONE_FALLBACK_KEY,
    GLOBAL_WEATHER_CACHE_KEY,
    SUPPLEMENTAL_WEATHER_POINTS,
    _capital_points_from_world_bank,
    _normalize_weather,
    _weather_url,
)


TEST_CACHES = {  # Testy nie powinny wymagać uruchomionego kontenera Redis.
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',  # Cache żyje tylko w procesie testowym.
        'LOCATION': 'niezmoknij-observations-tests',  # Osobna nazwa zapobiega kolizjom z innymi zestawami testów.
    }
}


@override_settings(CACHES=TEST_CACHES, LOCATION_WEATHER_CACHE_TTL=900)
class SavedLocationApiTests(APITestCase):
    """Sprawdza chronione operacje lokalizacji oraz historię pogody."""

    def setUp(self):
        # Tworzymy właściciela lokalizacji używanego w większości testów.
        self.user = get_user_model().objects.create_user(
            username='student',
            email='student@example.com',
            password='test-password-123',
        )
        # Drugi użytkownik pozwala sprawdzić izolację danych.
        self.other_user = get_user_model().objects.create_user(
            username='other-student',
            email='other@example.com',
            password='test-password-456',
        )
        # Każdy test zaczyna się bez pozostałości cache z wcześniejszego przypadku.
        cache.clear()

    def tearDown(self):
        # Czyścimy cache również po teście, aby nie wpływał na inne klasy.
        cache.clear()

    def authenticate(self, user=None):
        # force_authenticate testuje zachowanie uprawnień bez ręcznego budowania JWT w każdym przypadku.
        self.client.force_authenticate(user=user or self.user)

    def location_payload(self, **overrides):
        # Domyślny formularz opisuje poprawną lokalizację w Krakowie.
        payload = {
            'name': 'Kraków',
            'latitude': '50.064700',
            'longitude': '19.945000',
            'country': 'Polska',
            'region': 'Małopolskie',
            'description': 'Lokalizacja testowa',
        }
        # Nadpisania pozwalają zwięźle przygotować przypadki błędne.
        payload.update(overrides)
        # Zwracamy gotowy słownik do requestu JSON.
        return payload

    def create_location(self, user=None, **overrides):
        # Helper zapisuje lokalizację bezpośrednio w bazie dla testów odczytu i uprawnień.
        return SavedLocation.objects.create(
            user=user or self.user,
            name=overrides.get('name', 'Kraków'),
            latitude=overrides.get('latitude', '50.064700'),
            longitude=overrides.get('longitude', '19.945000'),
            country=overrides.get('country', 'Polska'),
            region=overrides.get('region', 'Małopolskie'),
            description=overrides.get('description', ''),
        )

    def open_meteo_payload(self):
        # Odpowiedź odwzorowuje pola current używane przez produkcyjny kod.
        return {
            'current': {
                'time': '2026-06-12T10:00',
                'temperature_2m': 22.4,
                'relative_humidity_2m': 61,
                'pressure_msl': 1014.6,
                'wind_speed_10m': 13.2,
                'weather_code': 2,
                'cloud_cover': 37,
            }
        }

    def test_anonymous_user_cannot_list_locations(self):
        # Nie ustawiamy uwierzytelnienia klienta.
        response = self.client.get('/api/locations/')

        # DRF powinien zażądać poprawnego tokenu użytkownika.
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_create_and_list_only_own_locations(self):
        # Drugi użytkownik ma punkt, którego właściciel testu nie powinien zobaczyć.
        self.create_location(
            user=self.other_user,
            name='Tokio',
            latitude='35.676200',
            longitude='139.650300',
            country='Japonia',
        )
        # Uwierzytelniamy głównego użytkownika.
        self.authenticate()

        # POST tworzy lokalizację przypisaną do request.user.
        create_response = self.client.post('/api/locations/', self.location_payload(), format='json')
        # GET pobiera listę punktów właściciela.
        list_response = self.client.get('/api/locations/')

        # Poprawny formularz powinien utworzyć zasób.
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        # Lista powinna zawierać tylko jedną własną lokalizację.
        self.assertEqual(len(list_response.data), 1)
        # Zwrócona nazwa potwierdza, że cudzy punkt został odfiltrowany.
        self.assertEqual(list_response.data[0]['name'], 'Kraków')
        # Baza przechowuje relację z użytkownikiem wynikającym z uwierzytelnienia.
        self.assertEqual(SavedLocation.objects.get(name='Kraków').user, self.user)

    def test_invalid_coordinates_are_rejected(self):
        # Uwierzytelniamy użytkownika przed wysłaniem chronionego formularza.
        self.authenticate()

        # Szerokość 95 przekracza maksymalną wartość geograficzną 90.
        response = self.client.post(
            '/api/locations/',
            self.location_payload(latitude='95.000000'),
            format='json',
        )

        # Walidator modelu powinien zwrócić błąd danych wejściowych.
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Niepoprawny request nie może utworzyć rekordu.
        self.assertEqual(SavedLocation.objects.count(), 0)

    def test_duplicate_coordinates_are_rejected_even_with_another_name(self):
        # Pierwszy punkt zajmuje współrzędne Krakowa dla głównego użytkownika.
        self.create_location()
        # Uwierzytelniamy tego samego właściciela.
        self.authenticate()

        # Drugi formularz używa innej nazwy, ale dokładnie tych samych współrzędnych.
        response = self.client.post(
            '/api/locations/',
            self.location_payload(name='Centrum Krakowa'),
            format='json',
        )

        # Reguła biznesowa powinna zablokować duplikat.
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # W bazie pozostaje tylko pierwszy rekord.
        self.assertEqual(SavedLocation.objects.count(), 1)

    def test_user_cannot_delete_another_users_location(self):
        # Tworzymy lokalizację należącą do drugiego użytkownika.
        foreign_location = self.create_location(user=self.other_user)
        # Request wykonuje główny użytkownik.
        self.authenticate()

        # Próba usunięcia używa poprawnego id, ale niewłaściwego właściciela.
        response = self.client.delete(f'/api/locations/{foreign_location.pk}/')

        # Neutralne 404 nie ujawnia, że cudzy zasób faktycznie istnieje.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # Rekord drugiego użytkownika pozostaje w bazie.
        self.assertTrue(SavedLocation.objects.filter(pk=foreign_location.pk).exists())

    @patch('observations.views._fetch_json')
    def test_weather_is_cached_and_snapshot_is_not_duplicated(self, fetch_json):
        # Mock zwraca deterministyczny pomiar bez połączenia z internetem.
        fetch_json.return_value = self.open_meteo_payload()
        # Tworzymy punkt, dla którego pobierzemy pogodę.
        location = self.create_location()
        # Uwierzytelniamy jego właściciela.
        self.authenticate()

        # Pierwszy request powinien pobrać dane i utworzyć snapshot.
        first_response = self.client.get(f'/api/locations/{location.pk}/weather/')
        # Drugi request powinien trafić do cache.
        second_response = self.client.get(f'/api/locations/{location.pk}/weather/')

        # Oba requesty powinny zakończyć się sukcesem.
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        # Pierwsza odpowiedź oznacza świeże pobranie.
        self.assertFalse(first_response.data['cached'])
        # Druga odpowiedź jawnie potwierdza trafienie cache.
        self.assertTrue(second_response.data['cached'])
        # Zewnętrzne API powinno zostać wywołane tylko raz.
        self.assertEqual(fetch_json.call_count, 1)
        # Historia nie może zawierać dwóch identycznych rekordów z okresu jednego TTL.
        self.assertEqual(WeatherSnapshot.objects.filter(location=location).count(), 1)
        # Snapshot powinien zachować zachmurzenie zwrócone przez źródło.
        self.assertEqual(first_response.data['weather']['cloud_cover'], 37)
        # Kod WMO powinien zostać zamieniony na czytelny opis.
        self.assertEqual(first_response.data['weather']['description'], 'Częściowe zachmurzenie')

    @patch('observations.views._fetch_json')
    def test_shared_coordinate_cache_creates_separate_history_for_each_user(self, fetch_json):
        # Jedna odpowiedź Open-Meteo powinna wystarczyć obu użytkownikom obserwującym ten sam punkt.
        fetch_json.return_value = self.open_meteo_payload()
        # Każdy użytkownik zapisuje własny rekord lokalizacji o tych samych współrzędnych.
        first_location = self.create_location(user=self.user, name='Kraków użytkownika 1')
        # Ograniczenie bazy dopuszcza ten sam punkt dla innego właściciela.
        second_location = self.create_location(user=self.other_user, name='Kraków użytkownika 2')

        # Pierwszy użytkownik pobiera dane z Open-Meteo i wypełnia współdzielony cache.
        self.authenticate(self.user)
        first_response = self.client.get(f'/api/locations/{first_location.pk}/weather/')
        # Drugi użytkownik prosi o te same współrzędne.
        self.authenticate(self.other_user)
        second_response = self.client.get(f'/api/locations/{second_location.pk}/weather/')

        # Pierwszy request jest świeżym pobraniem.
        self.assertFalse(first_response.data['cached'])
        # Drugi request korzysta z neutralnego pomiaru przechowywanego w cache.
        self.assertTrue(second_response.data['cached'])
        # Zewnętrzne API nadal zostało wywołane tylko raz.
        self.assertEqual(fetch_json.call_count, 1)
        # Pierwsza lokalizacja ma własny rekord historii.
        self.assertEqual(WeatherSnapshot.objects.filter(location=first_location).count(), 1)
        # Druga lokalizacja również ma własny rekord historii.
        self.assertEqual(WeatherSnapshot.objects.filter(location=second_location).count(), 1)
        # Id snapshotów muszą być różne, aby nie ujawniać relacji między kontami.
        self.assertNotEqual(first_response.data['weather']['id'], second_response.data['weather']['id'])

    def test_weather_history_is_sorted_and_protected_by_owner(self):
        # Tworzymy własną lokalizację oraz lokalizację drugiego użytkownika.
        own_location = self.create_location()
        # Cudzy punkt ma inne współrzędne, aby nie naruszyć ograniczenia unikalności.
        foreign_location = self.create_location(
            user=self.other_user,
            name='Warszawa',
            latitude='52.229700',
            longitude='21.012200',
        )
        # Zapisujemy jeden pomiar w historii własnej lokalizacji.
        WeatherSnapshot.objects.create(
            location=own_location,
            temperature='18.50',
            humidity=70,
            pressure=1010,
            wind_speed='8.20',
            cloud_cover=55,
            weather_code=3,
            description='Pochmurno',
            source='Open-Meteo',
            measured_at='2026-06-12T08:00:00Z',
        )
        # Uwierzytelniamy głównego użytkownika.
        self.authenticate()

        # Własna historia powinna być dostępna.
        own_response = self.client.get(f'/api/locations/{own_location.pk}/weather/history/')
        # Historia cudzego punktu powinna być ukryta.
        foreign_response = self.client.get(f'/api/locations/{foreign_location.pk}/weather/history/')

        # Własny endpoint zwraca zapisany pomiar.
        self.assertEqual(own_response.status_code, status.HTTP_200_OK)
        # Licznik powinien odpowiadać liczbie elementów w results.
        self.assertEqual(own_response.data['count'], 1)
        # Temperatura potwierdza poprawną serializację rekordu z relacji.
        self.assertEqual(own_response.data['results'][0]['temperature'], '18.50')
        # Cudzy zasób pozostaje niewidoczny.
        self.assertEqual(foreign_response.status_code, status.HTTP_404_NOT_FOUND)


@override_settings(CACHES=TEST_CACHES)
class DashboardApiTests(APITestCase):
    """Sprawdza agregacje, cache i izolację prywatnej części Dashboardu."""

    def setUp(self):
        # Pierwsze konto posiada własne lokalizacje widoczne po przesłaniu JWT.
        self.user = get_user_model().objects.create_user(
            username='dashboard-user',
            email='dashboard@example.com',
            password='test-password-123',
        )
        # Drugie konto pozwala wykryć przypadkowe ujawnienie cudzych lokalizacji.
        self.other_user = get_user_model().objects.create_user(
            username='dashboard-other',
            email='dashboard-other@example.com',
            password='test-password-456',
        )
        # Cache czyścimy przed każdym przypadkiem, aby pierwsza odpowiedź zawsze była świeża.
        cache.clear()

    def tearDown(self):
        # Usuwamy wpisy globalne i użytkowników po zakończeniu każdego testu.
        cache.clear()

    def create_earthquake(self, external_id, magnitude, hours_ago=1):
        # Helper tworzy kompletne zdarzenie w określonej odległości od bieżącego czasu.
        return EarthquakeEvent.objects.create(
            external_id=external_id,
            title=f'M{magnitude} - zdarzenie testowe',
            magnitude=str(magnitude),
            depth_km='12.50',
            latitude='50.060000',
            longitude='19.940000',
            place='Region testowy',
            event_time=timezone.now() - timedelta(hours=hours_ago),
            source='USGS',
            detail_url='https://earthquake.usgs.gov/',
        )

    def create_location_with_weather(self, user, name, latitude, longitude, temperature):
        # Lokalizacja jest przypisana do konkretnego właściciela.
        location = SavedLocation.objects.create(
            user=user,
            name=name,
            latitude=latitude,
            longitude=longitude,
            country='Polska',
            region='Testowy',
            description='Punkt Dashboardu',
        )
        # Snapshot pozwala sprawdzić, czy odpowiedź zawiera ostatnią pogodę.
        WeatherSnapshot.objects.create(
            location=location,
            temperature=str(temperature),
            humidity=58,
            pressure=1015,
            wind_speed='9.40',
            cloud_cover=24,
            weather_code=1,
            description='Przeważnie bezchmurnie',
            source='Open-Meteo',
            measured_at=timezone.now(),
        )
        # Zwracamy punkt do dalszych asercji.
        return location

    def test_public_dashboard_aggregates_recent_environmental_data(self):
        # Dwa zdarzenia mieszczą się w głównym zakresie ostatnich 24 godzin.
        self.create_earthquake('dashboard-recent-1', 3.4, hours_ago=2)
        self.create_earthquake('dashboard-recent-2', 5.8, hours_ago=6)
        # Starszy rekord może trafić do listy najnowszych, ale nie do statystyki dobowej.
        self.create_earthquake('dashboard-old', 7.2, hours_ago=30)
        # Jeden wulkan katalogowy zasila osobną kartę globalnego Dashboardu.
        VolcanicEvent.objects.create(
            external_id='dashboard-volcano',
            title='Wulkan testowy',
            volcano_name='Wulkan testowy',
            latitude='40.820000',
            longitude='14.420000',
            region='Europa',
            description='Test',
            event_time=timezone.now() - timedelta(days=3),
            source='Smithsonian GVP',
            detail_url='https://eonet.gsfc.nasa.gov/',
            status='open',
        )

        # Publiczny request nie przesyła żadnego użytkownika ani tokenu.
        response = self.client.get('/api/dashboard/summary/')

        # Endpoint powinien działać również dla niezalogowanej osoby.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Statystyka dobowa pomija zdarzenie sprzed trzydziestu godzin.
        self.assertEqual(response.data['earthquakes_last_24h'], 2)
        # Maksimum dotyczy wyłącznie zdarzeń w zakresie 24 godzin.
        self.assertEqual(response.data['max_magnitude_last_24h'], 5.8)
        # Licznik uwzględnia przygotowany rekord katalogu Smithsonian.
        self.assertEqual(response.data['volcanic_events'], 1)
        # Anonimowa odpowiedź nie zawiera żadnej prywatnej lokalizacji.
        self.assertEqual(response.data['saved_locations'], 0)
        # Rozkład powinien umieścić zdarzenia w dwóch odpowiednich przedziałach.
        self.assertEqual(
            [bucket['count'] for bucket in response.data['magnitude_distribution']],
            [0, 1, 0, 1, 0],
        )

    def test_authenticated_dashboard_contains_only_owners_locations(self):
        # Każde konto otrzymuje własny punkt i odmienny pomiar pogody.
        own_location = self.create_location_with_weather(
            self.user,
            'Kraków',
            '50.064700',
            '19.945000',
            '21.40',
        )
        self.create_location_with_weather(
            self.other_user,
            'Warszawa',
            '52.229700',
            '21.012200',
            '19.10',
        )
        # Uwierzytelniamy wyłącznie pierwszego właściciela.
        self.client.force_authenticate(user=self.user)

        # Dashboard rozpoznaje request.user tak samo jak moduł lokalizacji.
        response = self.client.get('/api/dashboard/summary/')

        # Prywatna część powinna zakończyć się sukcesem.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Licznik nie może obejmować punktu drugiego użytkownika.
        self.assertEqual(response.data['saved_locations'], 1)
        # Lista zawiera dokładnie własny rekord.
        self.assertEqual(response.data['locations'][0]['id'], own_location.pk)
        # Prefetch ostatniej pogody powinien dołączyć aktualną temperaturę.
        self.assertEqual(response.data['locations'][0]['latest_weather']['temperature'], '21.40')

    def test_dashboard_reports_cache_hit_and_location_post_invalidates_user_cache(self):
        # Uwierzytelniamy konto przed zbudowaniem jego prywatnego cache.
        self.client.force_authenticate(user=self.user)
        # Pierwszy request liczy obie części odpowiedzi.
        first_response = self.client.get('/api/dashboard/summary/')
        # Drugi request powinien skorzystać z obu gotowych wpisów.
        second_response = self.client.get('/api/dashboard/summary/')

        # Pierwszy odczyt nie pochodzi jeszcze z cache.
        self.assertFalse(first_response.data['cache']['global_data'])
        # Drugi odczyt potwierdza użycie publicznego wpisu.
        self.assertTrue(second_response.data['cache']['global_data'])
        # Drugi odczyt potwierdza również osobny cache użytkownika.
        self.assertTrue(second_response.data['cache']['user_data'])

        # Dodanie punktu przez właściwy endpoint powinno unieważnić tylko prywatną część.
        create_response = self.client.post(
            '/api/locations/',
            {
                'name': 'Gdańsk',
                'latitude': '54.352000',
                'longitude': '18.646600',
                'country': 'Polska',
                'region': 'Pomorskie',
                'description': 'Punkt dodany po zbudowaniu cache',
            },
            format='json',
        )
        # Poprawny formularz tworzy zasób.
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        # Kolejny Dashboard powinien przeliczyć lokalizacje, ale zachować globalne agregacje.
        refreshed_response = self.client.get('/api/dashboard/summary/')

        # Publiczny cache nadal jest poprawny i może zostać użyty.
        self.assertTrue(refreshed_response.data['cache']['global_data'])
        # Prywatna część została unieważniona przez perform_create.
        self.assertFalse(refreshed_response.data['cache']['user_data'])
        # Nowa wartość licznika potwierdza świeży odczyt bazy.
        self.assertEqual(refreshed_response.data['saved_locations'], 1)

    def test_dashboard_uses_authenticated_users_saved_range(self):
        # Tworzymy zdarzenie starsze niż doba, ale mieszczące się w zakresie siedmiu dni.
        self.create_earthquake('dashboard-week-event', 4.4, hours_ago=72)
        # Profil tworzy domyślny rekord preferencji dla użytkownika.
        from accounts.models import UserPreference  # Import lokalny utrzymuje test blisko używanego modelu konta.

        # Zapisujemy tygodniowy zakres jako trwałe ustawienie użytkownika.
        UserPreference.objects.create(user=self.user, dashboard_range_hours=168)
        # Request Dashboardu wykonuje właściciel preferencji.
        self.client.force_authenticate(user=self.user)

        # Endpoint nie wymaga parametru hours, ponieważ odczytuje relację użytkownika.
        response = self.client.get('/api/dashboard/summary/')

        # Odpowiedź powinna jawnie wskazać zastosowany zakres.
        self.assertEqual(response.data['range_hours'], 168)
        # Zdarzenie sprzed trzech dni powinno zostać uwzględnione.
        self.assertEqual(response.data['earthquakes_last_24h'], 1)


@override_settings(CACHES=TEST_CACHES)
class GlobalEnvironmentalApiTests(APITestCase):
    """Sprawdza odporność publicznych warstw na zmiany i awarie zewnętrznych API."""

    def setUp(self):
        # Każdy test rozpoczynamy bez poprzednich odpowiedzi zapisanych w pamięci.
        cache.clear()

    def tearDown(self):
        # Po teście usuwamy świeże i awaryjne dane, aby zachować pełną izolację.
        cache.clear()

    def test_global_weather_requests_and_returns_local_day_information(self):
        # Jeden punkt wystarcza do sprawdzenia parametrów budowanych dla całej paczki.
        points = [
            {
                'name': 'Barcelona',
                'country': 'Spain',
                'group': 'supplemental_city',
                'latitude': 41.3874,
                'longitude': 2.1686,
            }
        ]

        # Adres powinien prosić Open-Meteo o informację wyliczoną względem lokalnego słońca.
        weather_url = _weather_url(points)
        # Pole is_day jest niezbędne do wyboru słoneczka albo gwiazdy.
        self.assertIn('is_day', weather_url)
        # Strefa auto pozwala Open-Meteo dobrać lokalny czas dla każdej współrzędnej.
        self.assertIn('timezone=auto', weather_url)

        # Normalizujemy przykładową nocną odpowiedź o małym zachmurzeniu.
        normalized = _normalize_weather(
            points[0],
            {
                'current': {
                    'temperature_2m': 19,
                    'relative_humidity_2m': 70,
                    'pressure_msl': 1018,
                    'wind_speed_10m': 7,
                    'wind_gusts_10m': 12,
                    'precipitation': 0,
                    'weather_code': 0,
                    'cloud_cover': 5,
                    'is_day': 0,
                    'time': '2026-06-13T01:00',
                }
            },
        )

        # Frontend otrzymuje dokładnie wartość 0 oznaczającą noc.
        self.assertEqual(normalized['is_day'], 0)
        # Barcelona musi pozostać w rozszerzonej siatce punktów pogodowych.
        self.assertTrue(any(point['name'] == 'Barcelona' for point in SUPPLEMENTAL_WEATHER_POINTS))

    def world_bank_payload(self):
        # Pierwszy element odwzorowuje metadane paginacji Banku Światowego.
        metadata = {'page': 1, 'pages': 1, 'total': 2}
        # Drugi element zawiera jeden kraj i jeden agregat statystyczny do odfiltrowania.
        countries = [
            {
                'id': 'POL',
                'name': 'Poland',
                'region': {'id': 'ECS', 'value': 'Europe & Central Asia'},
                'capitalCity': 'Warsaw',
                'longitude': '21.02',
                'latitude': '52.26',
            },
            {
                'id': 'WLD',
                'name': 'World',
                'region': {'id': 'NA', 'value': 'Aggregates'},
                'capitalCity': '',
                'longitude': '',
                'latitude': '',
            },
        ]
        # Zwracamy dokładny dwuelementowy kształt odpowiedzi produkcyjnego API.
        return [metadata, countries]

    @patch('observations.views._fetch_json')
    def test_capitals_use_world_bank_shape_and_replace_invalid_cache(self, fetch_json):
        # Symulujemy stary, błędny słownik zapisany pod kluczem świeżych danych.
        cache.set(CAPITAL_POINTS_CACHE_KEY, {'success': False}, timeout=60)
        # Aktualne źródło zwraca poprawną odpowiedź Banku Światowego.
        fetch_json.return_value = self.world_bank_payload()

        # Helper powinien zignorować wadliwy cache i zbudować nową listę.
        points = _capital_points_from_world_bank()

        # Na liście pozostaje tylko rzeczywisty kraj ze stolicą.
        self.assertEqual(len(points), 1)
        # Nazwa stolicy potwierdza poprawne mapowanie pól nowego API.
        self.assertEqual(points[0]['name'], 'Warsaw')
        # Współrzędne są konwertowane z tekstu na liczby.
        self.assertEqual(points[0]['latitude'], 52.26)
        # Poprawna lista powinna zastąpić błędny wpis cache.
        self.assertEqual(cache.get(CAPITAL_POINTS_CACHE_KEY), points)
        # Ta sama lista zostaje zachowana jako długoterminowy fallback.
        self.assertEqual(cache.get(CAPITAL_POINTS_FALLBACK_KEY), points)

    @patch('observations.views._fetch_json')
    def test_capitals_return_empty_list_for_deprecated_api_error_shape(self, fetch_json):
        # Taki słownik zwracała wyłączona wersja REST Countries i wcześniej powodował błąd 500.
        fetch_json.return_value = {
            'success': False,
            'errors': [{'message': 'This API version has been deprecated.'}],
        }

        # Niepoprawny format źródła powinien zostać obsłużony bez wyjątku.
        points = _capital_points_from_world_bank()

        # Brak fallbacku daje pustą listę, dzięki czemu nadal działają punkty Polski i G20.
        self.assertEqual(points, [])

    @patch('observations.views._fetch_json')
    @patch('observations.views._all_weather_points')
    def test_storm_endpoint_survives_temporary_eonet_failure(self, all_weather_points, fetch_json):
        # Jedna lokalizacja wystarcza do sprawdzenia niezależności obu źródeł.
        all_weather_points.return_value = [
            {
                'name': 'Warszawa',
                'country': 'Polska',
                'group': 'poland_top_20',
                'latitude': 52.2297,
                'longitude': 21.0122,
            }
        ]
        # Poprawna odpowiedź Open-Meteo zawiera silny punkt burzowy.
        open_meteo_response = {
            'current': {
                'temperature_2m': 24,
                'precipitation': 12,
                'wind_gusts_10m': 95,
                'weather_code': 95,
                'cloud_cover': 90,
            }
        }
        # Pierwszy request do EONET zawodzi, ale drugi request pogodowy działa.
        fetch_json.side_effect = [
            HTTPError('https://eonet.example', 503, 'Service Unavailable', None, None),
            open_meteo_response,
        ]

        # Wywołujemy publiczny endpoint tak samo jak frontend.
        response = self.client.get('/api/storms/active/')

        # Awaria EONET nie może już wywrócić całej warstwy.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Punkt Open-Meteo powinien pozostać dostępny.
        self.assertEqual(response.data['counts']['storms'], 1)
        # Diagnostyka zachowuje informację o częściowej awarii źródła cyklonów.
        self.assertIn('EONET', response.data['source_errors'][0])

    @patch('observations.views._fetch_json')
    def test_storm_endpoint_reuses_global_weather_cache(self, fetch_json):
        # Cache pogody zawiera zmienne potrzebne do wyliczenia potencjału burzowego bez kolejnego requestu.
        cache.set(
            GLOBAL_WEATHER_CACHE_KEY,
            {
                'results': [
                    {
                        'name': 'Warszawa',
                        'country': 'Polska',
                        'group': 'poland_top_20',
                        'latitude': 52.2297,
                        'longitude': 21.0122,
                        'temperature': 24,
                        'precipitation': 12,
                        'wind_gusts': 95,
                        'weather_code': 95,
                        'cloud_cover': 90,
                    }
                ]
            },
            timeout=60,
        )
        # Jedyny zewnętrzny request dotyczy wtedy zdarzeń EONET.
        fetch_json.return_value = {'events': []}

        # Pobieramy warstwy burz i cyklonów po wcześniejszym załadowaniu pogody.
        response = self.client.get('/api/storms/active/')

        # Endpoint powinien zwrócić poprawną odpowiedź.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Punkt z cache spełnia warunek silnej burzy.
        self.assertEqual(response.data['counts']['storms'], 1)
        # Brak drugiego wywołania potwierdza, że Open-Meteo nie zostało odpytane ponownie.
        self.assertEqual(fetch_json.call_count, 1)

    @patch('observations.views._fetch_json')
    def test_cyclone_layer_uses_its_own_fallback_during_eonet_failure(self, fetch_json):
        # Zapisujemy ostatni poprawny marker niezależnie od cache punktów burzowych.
        cached_cyclones = [
            {
                'external_id': 'EONET_TEST',
                'name': 'Tropical Storm Test',
                'latitude': 12.8,
                'longitude': -89.1,
                'event_time': '2026-06-11T00:00:00Z',
                'source': 'NASA EONET',
                'kind': 'cyclone',
            }
        ]
        # Osobny klucz pozwala zachować cyklony mimo świeżych danych pogodowych.
        cache.set(CYCLONE_FALLBACK_KEY, cached_cyclones, timeout=60)
        # Gotowa pogoda zapobiega dodatkowemu requestowi do Open-Meteo.
        cache.set(
            GLOBAL_WEATHER_CACHE_KEY,
            {
                'results': [
                    {
                        'name': 'Warszawa',
                        'country': 'Polska',
                        'group': 'poland_top_20',
                        'latitude': 52.2297,
                        'longitude': 21.0122,
                        'temperature': 15,
                        'precipitation': 0,
                        'wind_gusts': 10,
                        'weather_code': 2,
                        'cloud_cover': 50,
                    }
                ]
            },
            timeout=60,
        )
        # Symulujemy chwilową odpowiedź 503 z NASA.
        fetch_json.side_effect = HTTPError('https://eonet.example', 503, 'Service Unavailable', None, None)

        # Frontend pobiera obie warstwy jednym requestem.
        response = self.client.get('/api/storms/active/')

        # Częściowa awaria nie może zmienić kodu odpowiedzi na błąd.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Ostatni cyklon pozostaje widoczny na mapie.
        self.assertEqual(response.data['counts']['cyclones'], 1)
        # Jawna flaga informuje, że zdarzenie nie pochodzi z bieżącego requestu.
        self.assertTrue(response.data['cyclones_stale'])


@override_settings(CACHES=TEST_CACHES)
class PersistentSynchronizationTests(APITestCase):
    """Sprawdza trwały import zdarzeń, idempotencję i administracyjne uruchamianie zadań."""

    def setUp(self):
        # Zwykły użytkownik pozwala potwierdzić, że synchronizacja nie jest publiczną operacją.
        self.user = get_user_model().objects.create_user(
            username='viewer',
            email='viewer@example.com',
            password='test-password-123',
        )
        # Użytkownik staff ma prawo uruchamiać zadania i czytać logi synchronizacji.
        self.admin_user = get_user_model().objects.create_user(
            username='operator',
            email='operator@example.com',
            password='test-password-456',
            is_staff=True,
        )
        # Cache jest czyszczony, aby testy nie zależały od kolejności wykonania.
        cache.clear()

    def tearDown(self):
        # Usuwamy techniczne wpisy z pamięci po każdym przypadku.
        cache.clear()

    def usgs_payload(self, magnitude=4.6):
        # Czas Unix w milisekundach odwzorowuje format oficjalnego GeoJSON USGS.
        event_timestamp = int(timezone.now().timestamp() * 1000)
        # Zwracamy minimalny kompletny dokument akceptowany przez normalizator.
        return {
            'features': [
                {
                    'id': 'usgs-test-1',
                    'properties': {
                        'title': 'M4.6 - testowe trzęsienie',
                        'place': 'Test Region',
                        'mag': magnitude,
                        'time': event_timestamp,
                        'url': 'https://earthquake.usgs.gov/earthquakes/eventpage/usgs-test-1',
                    },
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [19.94, 50.06, 12.5],
                    },
                }
            ]
        }

    def gvp_volcano_payload(self, title='Test Volcano'):
        # Warstwa wulkanów Smithsonian jest kolekcją obiektów GeoJSON.
        return {
            'type': 'FeatureCollection',
            'totalFeatures': 1,
            'features': [
                {
                    'type': 'Feature',
                    'geometry': {'type': 'Point', 'coordinates': [14.42, 40.82]},
                    'properties': {
                        'Volcano_Number': 211020,
                        'Volcano_Name': title,
                        'Country': 'Italy',
                        'Region': 'Mediterranean and Western Asia',
                        'Subregion': 'Italian Peninsula Volcanic Provinces',
                        'Primary_Volcano_Type': 'Stratovolcano',
                        'Elevation': 1281,
                        'Last_Eruption_Year': 1944,
                        'Geological_Summary': 'Testowe podsumowanie geologiczne.',
                        'Tectonic_Setting': 'Subduction zone',
                        'Geologic_Epoch': 'Holocene',
                        'Evidence_Category': 'Eruption Observed',
                        'Major_Rock_Type': 'Trachyte / Trachydacite',
                        'Primary_Photo_Link': 'https://example.com/volcano.jpg',
                        'Primary_Photo_Caption': 'Fotografia testowa.',
                    },
                }
            ],
        }

    def gvp_eruption_payload(self, latest_vei=3):
        # Osobna warstwa erupcji dostarcza VEI i jest łączona przez Volcano_Number.
        return {
            'type': 'FeatureCollection',
            'totalFeatures': 2,
            'features': [
                {
                    'type': 'Feature',
                    'geometry': None,
                    'properties': {
                        'Volcano_Number': 211020,
                        'Eruption_Number': 1001,
                        'StartDateYear': 1944,
                        'StartDateMonth': 3,
                        'StartDateDay': 18,
                        'ExplosivityIndexMax': latest_vei,
                    },
                },
                {
                    'type': 'Feature',
                    'geometry': None,
                    'properties': {
                        'Volcano_Number': 211020,
                        'Eruption_Number': 1000,
                        'StartDateYear': 79,
                        'StartDateMonth': 8,
                        'StartDateDay': 24,
                        'ExplosivityIndexMax': 5,
                    },
                },
            ],
        }

    @patch('observations.sync_services.fetch_json')
    def test_earthquake_sync_updates_existing_event_without_duplicate(self, fetch_json):
        # Pierwszy import zapisuje zdarzenie z początkową magnitudą.
        fetch_json.return_value = self.usgs_payload(magnitude=4.6)
        first_count = synchronize_earthquakes()
        # Drugi import używa tego samego external_id, ale nowszej magnitudy.
        fetch_json.return_value = self.usgs_payload(magnitude=4.9)
        second_count = synchronize_earthquakes()

        # Obie paczki zawierały po jednym poprawnym elemencie.
        self.assertEqual((first_count, second_count), (1, 1))
        # update_or_create powinno pozostawić dokładnie jeden rekord domenowy.
        self.assertEqual(EarthquakeEvent.objects.count(), 1)
        # Drugi import powinien zaktualizować wartość zamiast utworzyć duplikat.
        self.assertEqual(str(EarthquakeEvent.objects.get().magnitude), '4.9')
        # Każda próba synchronizacji ma własny, zakończony log audytowy.
        self.assertEqual(
            SyncJob.objects.filter(
                job_type=SyncJob.JobType.EARTHQUAKE,
                status=SyncJob.Status.SUCCESS,
            ).count(),
            2,
        )

    @patch('observations.sync_services.fetch_json')
    def test_volcano_sync_updates_existing_event_without_duplicate(self, fetch_json):
        # Pierwsza para odpowiedzi tworzy rekord i dołącza do niego historię VEI.
        fetch_json.side_effect = [
            self.gvp_volcano_payload(title='Test Volcano'),
            self.gvp_eruption_payload(latest_vei=3),
        ]
        synchronize_volcanic_events()
        # Druga para aktualizuje nazwę i VEI tego samego numeru Smithsonian.
        fetch_json.side_effect = [
            self.gvp_volcano_payload(title='Test Volcano Updated'),
            self.gvp_eruption_payload(latest_vei=4),
        ]
        synchronize_volcanic_events()

        # Stabilny Volcano_Number powinien chronić bazę przed duplikatem.
        self.assertEqual(VolcanicEvent.objects.count(), 1)
        # Aktualny tytuł potwierdza działanie update_or_create.
        self.assertEqual(VolcanicEvent.objects.get().title, 'Test Volcano Updated')
        # VEI ostatniej erupcji pochodzi z najnowszego rekordu historii.
        self.assertEqual(VolcanicEvent.objects.get().vei, 4)
        # Maksimum obejmuje również starszą, silniejszą erupcję testową.
        self.assertEqual(VolcanicEvent.objects.get().max_vei, 5)
        # Źródło danych nie może wskazywać dawnego integratora EONET.
        self.assertEqual(VolcanicEvent.objects.get().source, 'Smithsonian GVP')

    def test_earthquake_endpoint_reads_existing_database_record(self):
        # Tworzymy zdarzenie bezpośrednio, aby endpoint nie wykonywał requestu inicjalnego.
        EarthquakeEvent.objects.create(
            external_id='stored-earthquake',
            title='Zdarzenie zapisane w bazie',
            magnitude='5.2',
            depth_km='8.50',
            latitude='50.060000',
            longitude='19.940000',
            place='Polska test',
            event_time=timezone.now(),
            source='USGS',
            detail_url='',
        )

        # Filtry mają zostać wykonane przez ORM na istniejącym rekordzie.
        response = self.client.get('/api/earthquakes/?hours=24&min_magnitude=5&region=Polska')

        # Odczyt trwałych danych powinien zakończyć się bez kontaktu ze źródłem zewnętrznym.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Lista zawiera przygotowany rekord.
        self.assertEqual(response.data['count'], 1)
        # Metadane jawnie wskazują bazę oraz pierwotne źródło.
        self.assertEqual(response.data['source'], 'PostgreSQL / USGS')

    def test_earthquake_endpoint_applies_all_table_filters(self):
        # Bieżący czas jest wspólnym punktem odniesienia dla rekordów nowych i przeterminowanych.
        now = timezone.now()
        # Ten rekord spełnia zakres czasu, magnitudę, głębokość oraz wyszukiwany region.
        expected_event = EarthquakeEvent.objects.create(
            external_id='matching-earthquake',
            title='Dopasowane zdarzenie',
            magnitude='5.8',
            depth_km='42.00',
            latitude='37.750000',
            longitude='15.000000',
            place='Sycylia, Włochy',
            event_time=now - timedelta(hours=2),
            source='USGS',
            detail_url='',
        )
        # Zdarzenie jest zbyt głębokie i powinno zostać odrzucone przez filtr max_depth.
        EarthquakeEvent.objects.create(
            external_id='too-deep-earthquake',
            title='Zbyt głębokie zdarzenie',
            magnitude='6.1',
            depth_km='180.00',
            latitude='37.700000',
            longitude='15.100000',
            place='Sycylia, Włochy',
            event_time=now - timedelta(hours=1),
            source='USGS',
            detail_url='',
        )
        # Zdarzenie jest starsze niż siedem dni i powinno zostać odrzucone przez filtr hours.
        EarthquakeEvent.objects.create(
            external_id='too-old-earthquake',
            title='Zbyt stare zdarzenie',
            magnitude='6.4',
            depth_km='20.00',
            latitude='37.650000',
            longitude='15.200000',
            place='Sycylia, Włochy',
            event_time=now - timedelta(days=8),
            source='USGS',
            detail_url='',
        )
        # Rekord z innego regionu sprawdza tekstowe filtrowanie pola place.
        EarthquakeEvent.objects.create(
            external_id='other-region-earthquake',
            title='Inny region',
            magnitude='6.0',
            depth_km='30.00',
            latitude='35.000000',
            longitude='139.000000',
            place='Honsiu, Japonia',
            event_time=now - timedelta(hours=3),
            source='USGS',
            detail_url='',
        )

        # Frontend wysyła wszystkie filtry tabeli jako parametry query string.
        response = self.client.get(
            '/api/earthquakes/?hours=168&min_magnitude=5.5&max_depth=70&region=Sycylia'
        )

        # Poprawna kombinacja parametrów powinna zwrócić odpowiedź 200.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Po zastosowaniu wszystkich warunków powinien pozostać dokładnie jeden rekord.
        self.assertEqual(response.data['count'], 1)
        # Id wyniku potwierdza, że endpoint nie zwrócił podobnego, lecz niedopasowanego zdarzenia.
        self.assertEqual(response.data['results'][0]['id'], expected_event.pk)
        # Metadane odpowiedzi pozwalają frontendowi odtworzyć aktywne filtry.
        self.assertEqual(response.data['hours'], 168)
        # Maksymalna głębokość powinna pozostać zgodna z żądaniem użytkownika.
        self.assertEqual(response.data['max_depth'], 70.0)
        # Region powinien zostać zwrócony bez zmiany tekstu.
        self.assertEqual(response.data['region'], 'Sycylia')

    def test_volcanic_endpoint_filters_country_region_and_vei(self):
        # Tworzymy wulkan, który ma pozostać po wszystkich filtrach katalogowych.
        expected_event = VolcanicEvent.objects.create(
            external_id='matching-volcano',
            title='Etna',
            volcano_name='Etna',
            description='Aktywność testowa.',
            status='catalogued',
            latitude='37.748000',
            longitude='14.999000',
            country='Italy',
            region='Sycylia, Włochy',
            vei=4,
            max_vei=5,
            event_time=timezone.now() - timedelta(days=2),
            source='Smithsonian GVP',
            detail_url='',
        )
        # Wulkan w tym samym regionie ma zbyt niskie maksymalne VEI.
        VolcanicEvent.objects.create(
            external_id='low-vei-volcano',
            title='Wulkan o niższym VEI',
            volcano_name='Wulkan o niższym VEI',
            description='Rekord odrzucony przez próg VEI.',
            status='catalogued',
            latitude='37.748000',
            longitude='14.999000',
            country='Italy',
            region='Sycylia, Włochy',
            vei=2,
            max_vei=3,
            event_time=timezone.now() - timedelta(days=3),
            source='Smithsonian GVP',
            detail_url='',
        )
        # Silny wulkan z innego kraju sprawdza filtr country.
        VolcanicEvent.objects.create(
            external_id='other-country-volcano',
            title='Fuji',
            volcano_name='Fuji',
            description='Rekord z innego kraju.',
            status='catalogued',
            latitude='37.000000',
            longitude='15.000000',
            country='Japan',
            region='Honshu',
            vei=5,
            max_vei=5,
            event_time=timezone.now() - timedelta(days=20),
            source='Smithsonian GVP',
            detail_url='',
        )

        # Warstwa wulkaniczna może jednocześnie zawęzić kraj, region i historyczne VEI.
        response = self.client.get('/api/volcanoes/events/?country=Italy&region=Sycylia&has_vei=true&min_vei=4')

        # Poprawne filtry powinny zostać obsłużone przez relacyjną bazę danych.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # W odpowiedzi pozostaje tylko Etna spełniająca wszystkie warunki.
        self.assertEqual(response.data['count'], 1)
        # Stabilne id potwierdza właściwy rekord.
        self.assertEqual(response.data['results'][0]['id'], expected_event.pk)
        # Metadane potwierdzają, że frontend poprosił wyłącznie o rekordy posiadające VEI.
        self.assertTrue(response.data['has_vei'])
        # Źródło dokumentuje persystencję PostgreSQL oraz oficjalny katalog Smithsonian.
        self.assertEqual(response.data['source'], 'PostgreSQL / Smithsonian GVP')

    @patch('observations.tasks.sync_earthquakes_task.delay')
    def test_only_staff_user_can_queue_manual_sync(self, delay):
        # Pozorny wynik Celery udostępnia id zwracane przez endpoint.
        delay.return_value.id = 'celery-task-test'
        # Zwykły zalogowany użytkownik nie powinien uruchamiać kosztownego importu.
        self.client.force_authenticate(user=self.user)
        forbidden_response = self.client.post('/api/admin/sync/earthquakes/')
        # Administrator Django może dodać to samo zadanie do kolejki.
        self.client.force_authenticate(user=self.admin_user)
        accepted_response = self.client.post('/api/admin/sync/earthquakes/')

        # IsAdminUser blokuje konto bez flagi is_staff.
        self.assertEqual(forbidden_response.status_code, status.HTTP_403_FORBIDDEN)
        # Poprawna operacja asynchroniczna zwraca kod 202.
        self.assertEqual(accepted_response.status_code, status.HTTP_202_ACCEPTED)
        # Odpowiedź pozwala skorelować request z logami workera.
        self.assertEqual(accepted_response.data['task_id'], 'celery-task-test')
        # Zadanie powinno zostać przekazane do brokera tylko raz.
        delay.assert_called_once_with()

    def test_only_staff_user_can_read_sync_history(self):
        # Tworzymy zakończony wpis, który powinien być widoczny wyłącznie operatorowi.
        SyncJob.objects.create(
            job_type=SyncJob.JobType.EARTHQUAKE,
            status=SyncJob.Status.SUCCESS,
            items_fetched=12,
            started_at=timezone.now() - timedelta(minutes=2),
            finished_at=timezone.now() - timedelta(minutes=1),
        )
        # Zwykłe konto próbuje odczytać techniczne logi synchronizacji.
        self.client.force_authenticate(user=self.user)
        forbidden_response = self.client.get('/api/admin/sync/status/')
        # Następnie ten sam endpoint odpytuje użytkownik z flagą is_staff.
        self.client.force_authenticate(user=self.admin_user)
        accepted_response = self.client.get('/api/admin/sync/status/')

        # IsAdminUser powinien zablokować odczyt zwykłemu użytkownikowi.
        self.assertEqual(forbidden_response.status_code, status.HTTP_403_FORBIDDEN)
        # Operator powinien otrzymać historię bez błędu.
        self.assertEqual(accepted_response.status_code, status.HTTP_200_OK)
        # Licznik odpowiada przygotowanemu wpisowi audytowemu.
        self.assertEqual(accepted_response.data['count'], 1)
        # Typ zadania pozwala panelowi wyświetlić właściwą etykietę.
        self.assertEqual(
            accepted_response.data['results'][0]['job_type'],
            SyncJob.JobType.EARTHQUAKE,
        )
