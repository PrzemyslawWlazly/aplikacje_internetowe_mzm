"""Budowanie i cache'owanie podsumowania Dashboardu aplikacji."""

from datetime import timedelta  # Przedziały czasu ograniczają statystyki do użytecznego zakresu.

from django.core.cache import cache  # Redis przechowuje gotowe podsumowania przez pięć minut.
from django.db.models import Max  # Agregacja wylicza największą magnitudę bez pobierania wszystkich rekordów.
from django.utils import timezone  # Świadomy czas jest zgodny z polami DateTimeField projektu.

from .models import EarthquakeEvent, SavedLocation, SyncJob, VolcanicEvent  # Modele dostarczają dane Dashboardu.
from .serializers import EarthquakeEventSerializer, SavedLocationSerializer, saved_locations_queryset  # Serializery zachowują kontrakt API.


DASHBOARD_CACHE_TTL = 5 * 60  # Specyfikacja przewiduje pięciominutowy cache podsumowania.
DASHBOARD_ALLOWED_RANGES = (24, 168, 720)  # Zakresy odpowiadają 24 godzinom, 7 dniom i 30 dniom.


def dashboard_user_cache_key(user_id):
    """Buduje klucz prywatnej części Dashboardu dla jednego użytkownika."""

    return f'dashboard:user:{user_id}:v1'  # Id właściciela zapobiega mieszaniu danych między kontami.


def dashboard_global_cache_key(range_hours):
    """Buduje osobny klucz agregacji dla każdego dozwolonego zakresu."""

    return f'dashboard:global:{range_hours}h:v2'  # Zakres w kluczu zapobiega zwracaniu statystyk z innego okresu.


def invalidate_global_dashboard_cache():
    """Usuwa publiczne agregacje po synchronizacji danych środowiskowych."""

    cache.delete_many(  # Wszystkie warianty czasu zależą od tych samych zdarzeń środowiskowych.
        [dashboard_global_cache_key(range_hours) for range_hours in DASHBOARD_ALLOWED_RANGES]
    )


def invalidate_user_dashboard_cache(user_id):
    """Usuwa prywatne podsumowanie lokalizacji wskazanego użytkownika."""

    cache.delete(dashboard_user_cache_key(user_id))  # Unieważniamy wyłącznie dane jednego właściciela.


def _magnitude_distribution(earthquakes):
    """Dzieli magnitudy z ostatnich 24 godzin na czytelne przedziały wykresu."""

    distribution = [  # Stała kolejność pozwala frontendowi narysować stabilną oś wykresu.
        {'label': '0-2.4', 'count': 0},
        {'label': '2.5-3.9', 'count': 0},
        {'label': '4.0-5.4', 'count': 0},
        {'label': '5.5-6.9', 'count': 0},
        {'label': '7.0+', 'count': 0},
    ]
    for magnitude in earthquakes.values_list('magnitude', flat=True):  # Pobieramy tylko jedną potrzebną kolumnę.
        value = float(magnitude)  # Decimal zamieniamy na liczbę prostą do porównania.
        if value < 2.5:
            distribution[0]['count'] += 1  # Najsłabsze zdarzenia trafiają do pierwszego przedziału.
        elif value < 4.0:
            distribution[1]['count'] += 1  # Drugi przedział obejmuje często widoczne zdarzenia lokalne.
        elif value < 5.5:
            distribution[2]['count'] += 1  # Trzeci przedział grupuje umiarkowane trzęsienia.
        elif value < 7.0:
            distribution[3]['count'] += 1  # Czwarty przedział obejmuje silne zdarzenia.
        else:
            distribution[4]['count'] += 1  # Ostatnia grupa pozostaje otwarta od wartości 7.0.
    return distribution  # Gotowa lista jest bezpośrednio używana przez Recharts.


def _last_sync_payload():
    """Zwraca ostatni log każdego rodzaju synchronizacji."""

    result = {}  # Słownik będzie indeksowany prostymi nazwami używanymi przez frontend.
    job_names = {  # Mapowanie odcina frontend od technicznych wartości TextChoices.
        SyncJob.JobType.EARTHQUAKE: 'earthquakes',
        SyncJob.JobType.WEATHER: 'weather',
        SyncJob.JobType.VOLCANO: 'volcanoes',
    }
    for job_type, output_name in job_names.items():  # Każdy typ otrzymuje maksymalnie jeden najnowszy rekord.
        latest_job = SyncJob.objects.filter(job_type=job_type).order_by('-started_at').first()
        result[output_name] = (  # Brak uruchomienia ma jawny stan never zamiast niepełnego obiektu.
            {
                'status': latest_job.status,
                'started_at': latest_job.started_at.isoformat(),
                'finished_at': latest_job.finished_at.isoformat() if latest_job.finished_at else None,
                'items_fetched': latest_job.items_fetched,
                'error_message': latest_job.error_message,
            }
            if latest_job
            else {
                'status': 'NEVER',
                'started_at': None,
                'finished_at': None,
                'items_fetched': 0,
                'error_message': '',
            }
        )
    return result  # Stabilny kształt upraszcza prezentację trzech wierszy statusu.


def build_global_dashboard(range_hours=24):
    """Buduje publiczne statystyki Dashboardu albo odczytuje je z Redisa."""

    normalized_range = range_hours if range_hours in DASHBOARD_ALLOWED_RANGES else 24  # Nieznana wartość wraca do doby.
    cache_key = dashboard_global_cache_key(normalized_range)  # Każdy okres ma oddzielny wpis Redis.
    cached = cache.get(cache_key)  # Najpierw próbujemy ominąć zapytania agregujące.
    if cached is not None:
        return cached, True  # Flaga pozwala udokumentować realne użycie cache.

    now = timezone.now()  # Jeden wspólny czas zapewnia spójne granice wszystkich zapytań.
    range_start = now - timedelta(hours=normalized_range)  # Granica czasu wynika z preferencji użytkownika.
    recent_earthquakes = EarthquakeEvent.objects.filter(event_time__gte=range_start)  # Queryset zasila kilka agregacji.
    max_magnitude = recent_earthquakes.aggregate(value=Max('magnitude'))['value']  # PostgreSQL liczy maksimum.
    latest_events = EarthquakeEvent.objects.order_by('-event_time')[:6]  # Krótka lista mieści się w panelu.
    volcanic_events = VolcanicEvent.objects.all()  # Dashboard liczy pełny katalog wulkanów holoceńskich Smithsonian.

    payload = {  # Publiczna część nie zawiera żadnych danych kont użytkowników.
        'earthquakes_last_24h': recent_earthquakes.count(),
        'max_magnitude_last_24h': float(max_magnitude) if max_magnitude is not None else None,
        'range_hours': normalized_range,  # Frontend używa wartości w etykietach kart i wykresu.
        'volcanic_events': volcanic_events.count(),
        'magnitude_distribution': _magnitude_distribution(recent_earthquakes),
        'latest_earthquakes': EarthquakeEventSerializer(latest_events, many=True).data,
        'last_sync': _last_sync_payload(),
        'generated_at': now.isoformat(),
    }
    cache.set(cache_key, payload, timeout=DASHBOARD_CACHE_TTL)  # Redis przechowuje wariant zakresu pięć minut.
    return payload, False  # Pierwszy odczyt informuje, że agregacje zostały policzone.


def build_user_dashboard(user):
    """Buduje prywatne dane lokalizacji zalogowanego użytkownika."""

    if not user.is_authenticated:
        return {'saved_locations': 0, 'locations': []}, False  # Anonimowy Dashboard nie ma prywatnej części.

    cache_key = dashboard_user_cache_key(user.pk)  # Każde konto otrzymuje osobny klucz Redis.
    cached = cache.get(cache_key)  # Odczyt cache nie wykonuje zapytań do tabel lokalizacji i pomiarów.
    if cached is not None:
        return cached, True  # Trafienie cache jest raportowane w metadanych odpowiedzi.

    locations = saved_locations_queryset(user)  # Queryset prefetchuje ostatnią pogodę bez problemu N+1.
    serialized_locations = SavedLocationSerializer(locations, many=True).data  # Zwracamy wyłącznie rekordy właściciela.
    payload = {
        'saved_locations': len(serialized_locations),  # Licznik odpowiada dokładnie zwracanej liście.
        'locations': serialized_locations,  # Każda pozycja zawiera latest_weather albo null.
    }
    cache.set(cache_key, payload, timeout=DASHBOARD_CACHE_TTL)  # Prywatny wynik ma ten sam pięciominutowy TTL.
    return payload, False  # Flaga false oznacza świeży odczyt relacyjnej bazy.
