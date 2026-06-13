"""Usługi synchronizujące zewnętrzne dane środowiskowe z relacyjną bazą aplikacji."""

import json  # Moduł zamienia odpowiedzi tekstowe API na słowniki i listy Pythona.
from datetime import datetime, timedelta, timezone as datetime_timezone  # Klasy obsługują zakresy czasu i UTC.
from decimal import Decimal  # Decimal zachowuje wartości pomiarowe bez błędów binarnych float.
from urllib.parse import urlencode  # Funkcja bezpiecznie koduje parametry adresów URL.
from urllib.request import Request, urlopen  # Standardowa biblioteka wykonuje requesty bez dodatkowej zależności.

from django.core.cache import cache  # Redis przechowuje gotowe odpowiedzi odczytywane przez frontend.
from django.db import IntegrityError, transaction  # Transakcje i ograniczenia chronią spójność synchronizacji.
from django.utils import timezone  # Funkcja zwraca świadomy strefowo czas zgodny z Django.

from .models import EarthquakeEvent, SavedLocation, SyncJob, VolcanicEvent  # Modele są celem trwałej synchronizacji.
from .dashboard import invalidate_global_dashboard_cache, invalidate_user_dashboard_cache  # Synchronizacja odświeża agregacje.


USGS_EARTHQUAKE_URL = 'https://earthquake.usgs.gov/fdsnws/event/1/query'  # Oficjalne API zdarzeń sejsmicznych USGS.
GVP_WFS_URL = 'https://webservices.volcano.si.edu/geoserver/GVP-VOTW/ows'  # Oficjalny WFS Smithsonian udostępnia katalog GVP.
GVP_VOLCANO_LAYER = 'GVP-VOTW:Smithsonian_VOTW_Holocene_Volcanoes'  # Warstwa zawiera 1215 wulkanów holoceńskich.
GVP_ERUPTION_LAYER = 'GVP-VOTW:Smithsonian_VOTW_Holocene_Eruptions'  # Warstwa erupcji zawiera między innymi wartości VEI.
GVP_VOLCANO_LIMIT = 5000  # Limit jest większy od pełnego katalogu i pozostawia miejsce na jego rozwój.
GVP_ERUPTION_LIMIT = 20000  # Historia erupcji jest większa, dlatego pobieramy obszerniejszą paczkę.
REQUEST_TIMEOUT = 60  # Pełny katalog GVP jest większy od zwykłej odpowiedzi pogodowej i potrzebuje dłuższego limitu.


def fetch_json(url):
    """Pobiera odpowiedź JSON z zewnętrznego API."""

    request = Request(url, headers={'User-Agent': 'NieZmoknij/0.2'})  # Jawny klient ułatwia diagnostykę źródła.
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:  # Połączenie ma limit, więc worker nie zawisa bez końca.
        payload = response.read().decode('utf-8')  # Bajty odpowiedzi dekodujemy jako tekst UTF-8.
    return json.loads(payload)  # Parser zwraca listę albo słownik zależnie od API.


def earthquake_source_url(hours=24 * 30, min_magnitude=0):
    """Buduje adres USGS dla zadanej historii i minimalnej magnitudy."""

    start_time = timezone.now() - timedelta(hours=hours)  # Synchronizacja pobiera tylko potrzebny zakres czasowy.
    query = urlencode(  # Parametry tworzymy ze słownika, aby uniknąć błędów ręcznego sklejania.
        {
            'format': 'geojson',  # GeoJSON zawiera współrzędne i właściwości w jednym dokumencie.
            'starttime': start_time.isoformat(),  # USGS przyjmuje czas w formacie ISO 8601.
            'minmagnitude': min_magnitude,  # Dolny próg ogranicza liczbę bardzo słabych zdarzeń.
            'orderby': 'time',  # Najnowsze rekordy są pierwsze.
            'limit': 2000,  # Limit wystarcza dla demonstracyjnej historii i chroni pamięć workera.
        }
    )
    return f'{USGS_EARTHQUAKE_URL}?{query}'  # Zwracamy kompletny adres requestu.


def normalize_earthquake(feature):
    """Normalizuje pojedynczy obiekt GeoJSON USGS do pól modelu EarthquakeEvent."""

    properties = feature.get('properties') or {}  # Dane opisowe znajdują się w properties.
    geometry = feature.get('geometry') or {}  # Współrzędne znajdują się w geometry.
    coordinates = geometry.get('coordinates') or [None, None, None]  # GeoJSON używa kolejności longitude, latitude, depth.
    event_timestamp = properties.get('time')  # USGS zwraca czas jako liczbę milisekund Unix.
    event_time = (  # Czas zamieniamy na świadomy datetime UTC wymagany przez model.
        datetime.fromtimestamp(event_timestamp / 1000, tz=datetime_timezone.utc)
        if event_timestamp is not None
        else None
    )
    magnitude = properties.get('mag')  # Magnituda może być pusta w niekompletnym rekordzie źródłowym.
    if not feature.get('id') or magnitude is None or event_time is None or coordinates[0] is None or coordinates[1] is None:
        return None  # Rekordu bez klucza, czasu lub położenia nie można bezpiecznie utrwalić.
    return {
        'external_id': str(feature['id']),  # Stabilne id służy jako klucz operacji update_or_create.
        'defaults': {
            'title': str(properties.get('title') or properties.get('place') or 'Trzęsienie ziemi')[:255],
            'magnitude': Decimal(str(magnitude)),  # Decimal jest zgodny z polem modelu.
            'depth_km': Decimal(str(coordinates[2])) if coordinates[2] is not None else None,
            'latitude': Decimal(str(coordinates[1])),  # Drugi element GeoJSON to szerokość.
            'longitude': Decimal(str(coordinates[0])),  # Pierwszy element GeoJSON to długość.
            'place': str(properties.get('place') or '')[:255],  # Opis miejsca mieści się w limicie modelu.
            'event_time': event_time,  # Zdarzenie zachowuje rzeczywisty czas wystąpienia.
            'source': 'USGS',  # Źródło jest jawne w bazie i odpowiedzi API.
            'detail_url': str(properties.get('url') or ''),  # Link prowadzi do oficjalnej strony zdarzenia.
        },
    }


def gvp_source_url(layer_name, max_features):
    """Buduje adres WFS zwracający pełną warstwę Smithsonian jako GeoJSON."""

    query = urlencode(  # Standardowe parametry WFS są kodowane, aby dwukropek i slash pozostały bezpieczne.
        {
            'service': 'WFS',  # Web Feature Service udostępnia obiekty geograficzne.
            'version': '1.0.0',  # Wersja 1.0 używa parametru maxFeatures obsługiwanego przez GeoServer GVP.
            'request': 'GetFeature',  # Żądamy właściwych rekordów, a nie samego opisu schematu.
            'typeName': layer_name,  # Nazwa wybiera katalog wulkanów albo historię erupcji.
            'outputFormat': 'application/json',  # GeoJSON jest bezpośrednio obsługiwany przez parser aplikacji.
            'maxFeatures': max_features,  # Jeden kontrolowany request pobiera cały obecny katalog.
        }
    )
    return f'{GVP_WFS_URL}?{query}'  # Zwracamy kompletny oficjalny adres źródła.


def _integer_or_none(value):
    """Zamienia liczbę ze źródła na int albo zwraca None dla wartości nieznanej."""

    if value in (None, ''):  # Puste pole w katalogu oznacza brak danych.
        return None  # Nie zastępujemy braku danych sztucznym zerem.
    try:
        return int(float(value))  # float obsługuje również tekst typu „4.0”.
    except (TypeError, ValueError):
        return None  # Tekst „Unknown” albo „No Data” pozostaje wartością nieznaną.


def _vei_or_none(value):
    """Waliduje pojedynczą wartość Volcanic Explosivity Index."""

    parsed = _integer_or_none(value)  # Najpierw normalizujemy format liczby.
    if parsed is None or parsed < 0 or parsed > 8:  # Klasyczna skala VEI mieści się od 0 do 8.
        return None  # Niepoprawna wartość źródłowa nie trafia do modelu.
    return parsed  # Poprawny indeks może zostać zapisany w PositiveSmallIntegerField.


def _feature_collection(payload, source_name):
    """Sprawdza kompletność odpowiedzi GeoJSON przed zmianą danych w bazie."""

    features = payload.get('features') if isinstance(payload, dict) else None  # GeoJSON przechowuje rekordy w features.
    if not isinstance(features, list):  # Brak listy zwykle oznacza komunikat błędu GeoServera.
        raise ValueError(f'{source_name} zwrócił niepoprawny format GeoJSON.')
    total_features = _integer_or_none(payload.get('totalFeatures'))  # GeoServer podaje pełną liczbę dopasowań.
    if total_features is not None and total_features > len(features):  # Nie wolno usuwać danych po uciętej odpowiedzi.
        raise ValueError(
            f'{source_name} zwrócił tylko {len(features)} z {total_features} rekordów. '
            'Zwiększ limit WFS przed synchronizacją.'
        )
    return features  # Dopiero kompletna lista może zostać użyta w transakcji.


def eruption_summary_by_volcano(features):
    """Łączy historię erupcji w podsumowanie VEI dla każdego numeru wulkanu."""

    summaries = {}  # Kluczem słownika jest stabilny numer Volcano_Number.
    for feature in features:  # Każda pozycja opisuje jedną erupcję, a nie cały wulkan.
        properties = feature.get('properties') or {}  # Dane erupcji znajdują się w properties GeoJSON.
        volcano_number = str(properties.get('Volcano_Number') or '').strip()  # Numer łączy obie warstwy WFS.
        if not volcano_number:  # Rekordu bez klucza nie można przypisać do katalogu.
            continue  # Pomijamy tylko wadliwy element, nie całą paczkę.
        start_year = _integer_or_none(  # Rok pozwala wskazać ostatnią erupcję.
            properties.get('StartDateYear', properties.get('Start_Year'))
        )
        start_month = _integer_or_none(  # WFS 5.3.6 używa nazwy StartDateMonth.
            properties.get('StartDateMonth', properties.get('Start_Month'))
        ) or 0  # Brak miesiąca sortujemy przed znanym miesiącem tego samego roku.
        start_day = _integer_or_none(  # WFS 5.3.6 używa nazwy StartDateDay.
            properties.get('StartDateDay', properties.get('Start_Day'))
        ) or 0  # Dzień doprecyzowuje kolejność erupcji.
        eruption_number = _integer_or_none(properties.get('Eruption_Number')) or 0  # Numer rozstrzyga ten sam dzień.
        vei = _vei_or_none(  # Aktualna warstwa nazywa pole ExplosivityIndexMax, a fallback wspiera starszy schemat.
            properties.get('ExplosivityIndexMax', properties.get('VEI'))
        )
        sort_key = (start_year if start_year is not None else -100000, start_month, start_day, eruption_number)
        summary = summaries.setdefault(  # Pierwsza erupcja tworzy neutralne podsumowanie wulkanu.
            volcano_number,
            {'last_sort_key': (-100000, 0, 0, 0), 'last_year': None, 'last_vei': None, 'max_vei': None},
        )
        if vei is not None:  # Maksimum liczymy wyłącznie z rzeczywiście sklasyfikowanych erupcji.
            summary['max_vei'] = vei if summary['max_vei'] is None else max(summary['max_vei'], vei)
        if sort_key > summary['last_sort_key']:  # Najnowsza data zastępuje poprzednią erupcję.
            summary['last_sort_key'] = sort_key  # Klucz zachowujemy tylko na czas normalizacji.
            summary['last_year'] = start_year  # Rok może być ujemny dla erupcji BCE.
            summary['last_vei'] = vei  # Brak VEI ostatniej erupcji pozostaje jawny.
    return summaries  # Słownik pozwala wzbogacić 1215 wulkanów w czasie liniowym.


def normalize_gvp_volcano(feature, eruption_summaries):
    """Normalizuje wulkan GVP i dołącza VEI z osobnej warstwy erupcji."""

    properties = feature.get('properties') or {}  # Opis katalogowy znajduje się w properties.
    geometry = feature.get('geometry') or {}  # GeoJSON przechowuje współrzędne w osobnym obiekcie.
    coordinates = geometry.get('coordinates') or []  # Kolejność GeoJSON to longitude, latitude.
    volcano_number = str(properties.get('Volcano_Number') or '').strip()  # Numer GVP jest stabilnym kluczem.
    volcano_name = str(properties.get('Volcano_Name') or '').strip()  # Nazwa jest główną etykietą mapy.
    if geometry.get('type') != 'Point' or len(coordinates) < 2 or not volcano_number or not volcano_name:
        return None  # Niepełnego rekordu nie można poprawnie zaznaczyć na mapie.
    summary = eruption_summaries.get(volcano_number, {})  # Nie każdy wulkan ma erupcję z określonym VEI.
    last_eruption_year = summary.get('last_year')  # Historia erupcji ma pierwszeństwo przed skrótem katalogowym.
    if last_eruption_year is None:
        last_eruption_year = _integer_or_none(properties.get('Last_Eruption_Year'))  # Fallback pochodzi z warstwy wulkanów.
    event_time = None  # Datetime nie obsługuje roku zerowego ani lat BCE.
    if last_eruption_year is not None and 1 <= last_eruption_year <= 9999:
        event_time = datetime(last_eruption_year, 1, 1, tzinfo=datetime_timezone.utc)  # Pomocnicza data służy zgodności API.
    detail_url = f'https://volcano.si.edu/volcano.cfm?vn={volcano_number}'  # Oficjalna karta zawiera pełny opis i raporty.
    return {
        'external_id': volcano_number,  # Numer trafia do update_or_create.
        'defaults': {
            'title': volcano_name[:255],  # Tytuł i nazwa są zgodne dla katalogu wulkanów.
            'volcano_name': volcano_name[:160],  # Nazwa podstawowa pochodzi bezpośrednio ze Smithsonian.
            'latitude': Decimal(str(coordinates[1])),  # Drugi element to szerokość geograficzna.
            'longitude': Decimal(str(coordinates[0])),  # Pierwszy element to długość geograficzna.
            'country': str(properties.get('Country') or '')[:120],  # Kraj pochodzi z klasyfikacji GVP.
            'region': str(properties.get('Subregion') or properties.get('Region') or '')[:160],  # Preferujemy dokładniejszy podregion.
            'volcano_type': str(
                properties.get('Primary_Volcano_Type')
                or properties.get('Volcanic_Landform')
                or ''
            )[:120],  # Typ podstawowy jest czytelniejszy od ogólnej formy.
            'elevation_m': _integer_or_none(properties.get('Elevation')),  # Wysokość może być dodatnia lub ujemna.
            'last_eruption_year': last_eruption_year,  # Osobne pole poprawnie przechowuje także lata BCE.
            'vei': summary.get('last_vei'),  # VEI ostatniej erupcji może pozostać nieznane.
            'max_vei': summary.get('max_vei'),  # Maksimum pochodzi ze wszystkich sklasyfikowanych erupcji.
            'tectonic_setting': str(properties.get('Tectonic_Setting') or '')[:180],  # Kontekst tektoniczny.
            'geologic_epoch': str(properties.get('Geologic_Epoch') or '')[:80],  # Katalog jest obecnie holoceński.
            'evidence_category': str(properties.get('Evidence_Category') or '')[:120],  # Rodzaj dowodu aktywności.
            'rock_type': str(properties.get('Major_Rock_Type') or '')[:160],  # Dominujący skład skał.
            'description': str(properties.get('Geological_Summary') or ''),  # Pełne podsumowanie pozostaje tekstem.
            'event_time': event_time,  # Pomocnicza data jest pusta dla lat BCE i nieznanych.
            'source': 'Smithsonian GVP',  # Źródło jest widoczne w bazie oraz interfejsie.
            'detail_url': detail_url,  # Link prowadzi do oficjalnej karty GVP.
            'photo_url': str(properties.get('Primary_Photo_Link') or ''),  # Zdjęcie jest opcjonalne.
            'photo_caption': str(properties.get('Primary_Photo_Caption') or ''),  # Podpis wyjaśnia fotografię.
            'status': 'catalogued',  # Wpis w katalogu nie oznacza bieżącego alarmu ani erupcji.
        },
    }


def _start_sync_job(job_type):
    """Tworzy log rozpoczynanej synchronizacji."""

    return SyncJob.objects.create(  # Osobny rekord pozwala panelowi pokazać przebieg i błędy.
        job_type=job_type,  # Typ odróżnia pogodę, sejsmikę i wulkany.
        status=SyncJob.Status.RUNNING,  # Zadanie zaczyna w stanie trwającym.
        started_at=timezone.now(),  # Czas startu zapisujemy przed requestem zewnętrznym.
    )


def _finish_sync_job(job, item_count):
    """Oznacza synchronizację jako zakończoną sukcesem."""

    job.status = SyncJob.Status.SUCCESS  # Sukces jest końcowym stanem zadania.
    job.finished_at = timezone.now()  # Czas końca pozwala policzyć czas działania.
    job.items_fetched = item_count  # Licznik opisuje liczbę przetworzonych rekordów.
    job.error_message = ''  # Poprzedni komunikat nie powinien pozostać po sukcesie.
    job.save(update_fields=('status', 'finished_at', 'items_fetched', 'error_message', 'updated_at'))  # Zapisujemy tylko zmiany.


def _fail_sync_job(job, error):
    """Zapisuje błąd synchronizacji i ponownie zgłasza wyjątek wywołującemu."""

    job.status = SyncJob.Status.FAILED  # Panel administratora rozpozna zadanie zakończone błędem.
    job.finished_at = timezone.now()  # Nieudane zadanie również ma czas końca.
    job.error_message = str(error)[:4000]  # Ograniczamy tekst, aby log nie urósł bez kontroli.
    job.save(update_fields=('status', 'finished_at', 'error_message', 'updated_at'))  # Utrwalamy diagnostykę.


def synchronize_earthquakes(hours=24 * 30, min_magnitude=0):
    """Pobiera zdarzenia USGS i idempotentnie zapisuje je w bazie."""

    job = _start_sync_job(SyncJob.JobType.EARTHQUAKE)  # Każda próba ma własny log.
    try:
        payload = fetch_json(earthquake_source_url(hours, min_magnitude))  # Pobieramy pełny dokument GeoJSON.
        features = payload.get('features') if isinstance(payload, dict) else None  # Odpowiedź powinna zawierać listę features.
        if not isinstance(features, list):  # Zmiana formatu źródła nie może stworzyć pozornego sukcesu.
            raise ValueError('USGS zwrócił niepoprawny format danych sejsmicznych.')
        item_count = 0  # Licznik obejmuje poprawnie znormalizowane rekordy.
        with transaction.atomic():  # Paczka zmian zostaje zapisana spójnie.
            for feature in features:  # Każde zdarzenie może utworzyć albo zaktualizować istniejący rekord.
                normalized = normalize_earthquake(feature)  # Normalizator odrzuca niepełne dane.
                if normalized is None:  # Niepoprawny rekord nie blokuje pozostałych zdarzeń.
                    continue  # Przechodzimy do kolejnego elementu.
                EarthquakeEvent.objects.update_or_create(**normalized)  # External ID gwarantuje idempotencję.
                item_count += 1  # Zwiększamy licznik przetworzonych rekordów.
        _finish_sync_job(job, item_count)  # Log zapisuje sukces i liczbę elementów.
        invalidate_global_dashboard_cache()  # Statystyki sejsmiczne muszą uwzględnić nową paczkę.
        return item_count  # Wynik jest używany przez Celery i endpoint ręczny.
    except Exception as error:
        _fail_sync_job(job, error)  # Błąd trafia do tabeli SyncJob.
        raise  # Wyjątek pozostaje widoczny dla Celery albo endpointu inicjalnego.


def synchronize_volcanic_events(days=None):
    """Pobiera pełny katalog wulkanów i erupcji Smithsonian GVP."""

    job = _start_sync_job(SyncJob.JobType.VOLCANO)  # Rejestrujemy początek synchronizacji wulkanów.
    try:
        volcano_payload = fetch_json(gvp_source_url(GVP_VOLCANO_LAYER, GVP_VOLCANO_LIMIT))  # Pobieramy wszystkie wulkany.
        eruption_payload = fetch_json(gvp_source_url(GVP_ERUPTION_LAYER, GVP_ERUPTION_LIMIT))  # Pobieramy historię z VEI.
        volcanoes = _feature_collection(volcano_payload, 'Katalog wulkanów GVP')  # Walidujemy kompletność katalogu.
        eruptions = _feature_collection(eruption_payload, 'Katalog erupcji GVP')  # Walidujemy kompletność erupcji.
        eruption_summaries = eruption_summary_by_volcano(eruptions)  # Łączymy ostatnie i maksymalne VEI z numerem GVP.
        imported_ids = []  # Lista pozwala po sukcesie usunąć stare rekordy EONET i demo.
        with transaction.atomic():  # Aktualizacja katalogu i usunięcie starych rekordów są jedną operacją.
            for feature in volcanoes:  # Iterujemy po pełnej warstwie wulkanów holoceńskich.
                normalized = normalize_gvp_volcano(feature, eruption_summaries)  # Dołączamy podsumowanie erupcji.
                if normalized is None:  # Wielokąty i niepełne rekordy nie pasują do obecnego modelu.
                    continue  # Pomijamy je bez zatrzymywania synchronizacji.
                VolcanicEvent.objects.update_or_create(**normalized)  # External ID zapobiega duplikatom.
                imported_ids.append(normalized['external_id'])  # Zapamiętujemy rekord należący do aktualnego katalogu.
            if not imported_ids:  # Pusta poprawna transakcja mogłaby przypadkowo usunąć wszystkie dane.
                raise ValueError('Katalog GVP nie zawiera żadnego poprawnego wulkanu.')
            VolcanicEvent.objects.exclude(external_id__in=imported_ids).delete()  # Zastępujemy dane demo i EONET.
        item_count = len(imported_ids)  # Licznik odpowiada liczbie dostępnych markerów na mapie.
        _finish_sync_job(job, item_count)  # Zapisujemy sukces synchronizacji.
        invalidate_global_dashboard_cache()  # Licznik wulkanów i status synchronizacji wymagają przeliczenia.
        return item_count  # Licznik trafia do wyniku zadania Celery.
    except Exception as error:
        _fail_sync_job(job, error)  # Zachowujemy treść błędu do panelu administratora.
        raise  # Celery oznaczy zadanie jako nieudane.


def synchronize_saved_location_weather():
    """Odświeża pogodę wszystkich zapisanych lokalizacji i zapisuje historię."""

    job = _start_sync_job(SyncJob.JobType.WEATHER)  # Synchronizacja pogodowa otrzymuje osobny log.
    item_count = 0  # Licznik informuje, ile lokalizacji otrzymało poprawny pomiar.
    try:
        from .views import (  # Import lokalny zapobiega cyklowi modułów podczas startu Django.
            _create_weather_snapshot,
            _fetch_json,
            _saved_location_cache_key,
            _saved_location_weather_url,
            _weather_cache_payload,
        )

        for location in SavedLocation.objects.all().iterator():  # Iterator ogranicza pamięć przy większej liczbie punktów.
            api_data = _fetch_json(_saved_location_weather_url(location))  # Każda lokalizacja otrzymuje aktualny pomiar.
            try:
                snapshot = _create_weather_snapshot(location, api_data)  # Wspólny helper waliduje i zapisuje dane.
            except IntegrityError:
                continue  # Równoległy request mógł już zapisać dokładnie ten sam pomiar.
            cache.set(  # Redis otrzymuje neutralny payload współdzielony po współrzędnych.
                _saved_location_cache_key(location),
                _weather_cache_payload(snapshot),
                timeout=15 * 60,
            )
            item_count += 1  # Poprawny snapshot zwiększa licznik.
            invalidate_user_dashboard_cache(location.user_id)  # Ostatnia pogoda właściciela zmieniła się.
        _finish_sync_job(job, item_count)  # Log przechowuje wynik całej synchronizacji.
        invalidate_global_dashboard_cache()  # Globalny panel pokazuje czas ostatniej synchronizacji pogody.
        return item_count  # Celery pokaże liczbę odświeżonych lokalizacji.
    except Exception as error:
        _fail_sync_job(job, error)  # Awaria źródła lub bazy trafia do tabeli logów.
        raise  # Worker zachowuje standardowy stan FAILURE.
