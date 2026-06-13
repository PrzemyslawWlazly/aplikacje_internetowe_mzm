from django.db.models import Prefetch  # Prefetch pozwala pobrać ostatnie pomiary bez zapytań N+1.
from drf_spectacular.utils import extend_schema_field  # Dekorator opisuje pole wyliczane w schemacie OpenAPI.
from rest_framework import serializers  # Serializery walidują wejście i zamieniają modele na JSON.

from .models import (  # Serializery obejmują zasoby użytkownika, zdarzenia i logi synchronizacji.
    EarthquakeEvent,
    SavedLocation,
    SyncJob,
    VolcanicEvent,
    WeatherSnapshot,
)


class WeatherSnapshotSerializer(serializers.ModelSerializer):
    """Zamienia historyczny pomiar pogodowy na odpowiedź API."""

    class Meta:
        model = WeatherSnapshot  # Serializer opisuje model pojedynczego pomiaru.
        fields = (
            'id',  # Identyfikator pozwala rozróżnić pomiary w historii.
            'temperature',  # Temperatura jest podawana w stopniach Celsjusza.
            'humidity',  # Wilgotność jest wartością procentową.
            'pressure',  # Ciśnienie pochodzi z poziomu morza w hPa.
            'wind_speed',  # Prędkość wiatru pochodzi z wysokości 10 metrów.
            'cloud_cover',  # Zachmurzenie jest wartością od 0 do 100 procent.
            'weather_code',  # Kod WMO umożliwia dalszą interpretację warunków.
            'description',  # Czytelny polski opis jest wyliczany podczas pobierania.
            'source',  # Źródło danych pozostaje jawne dla użytkownika.
            'measured_at',  # Czas pochodzi z zewnętrznego API.
            'created_at',  # Czas zapisu pokazuje, kiedy backend utrwalił pomiar.
        )
        read_only_fields = fields  # Snapshoty powstają wyłącznie przez endpoint pogodowy.


class SavedLocationSerializer(serializers.ModelSerializer):
    """Waliduje lokalizację użytkownika i zwraca jej ostatni pomiar."""

    latest_weather = serializers.SerializerMethodField()  # Pole nie istnieje w tabeli, tylko wynika z relacji.

    class Meta:
        model = SavedLocation  # Serializer odpowiada tabeli zapisanych lokalizacji.
        fields = (
            'id',  # Id służy do usuwania oraz pobierania pogody i historii.
            'name',  # Nazwa jest widoczna w interfejsie użytkownika.
            'latitude',  # Szerokość jest walidowana przez reguły modelu od -90 do 90.
            'longitude',  # Długość jest walidowana przez reguły modelu od -180 do 180.
            'country',  # Kraj jest opcjonalną informacją opisową.
            'region',  # Region pomaga doprecyzować położenie.
            'description',  # Użytkownik może dopisać własną notatkę.
            'latest_weather',  # Ostatni snapshot pozwala wyświetlić listę bez dodatkowych requestów.
            'created_at',  # Data utworzenia przydaje się podczas prezentacji relacyjnej bazy.
            'updated_at',  # Data aktualizacji jest zarządzana automatycznie przez Django.
        )
        read_only_fields = (
            'id',  # Klucz główny nadaje baza danych.
            'latest_weather',  # Pomiar nie może zostać przesłany w formularzu lokalizacji.
            'created_at',  # Klient nie ustawia znaczników czasu.
            'updated_at',  # Klient nie ustawia znaczników czasu.
        )

    def validate_name(self, value):
        # Usuwamy zewnętrzne spacje, aby sama spacja nie była poprawną nazwą.
        cleaned_value = value.strip()
        # Pusta nazwa nie pomaga rozpoznać lokalizacji w panelu.
        if not cleaned_value:
            raise serializers.ValidationError('Nazwa lokalizacji nie może być pusta.')
        # Zwracamy oczyszczoną wartość do dalszej walidacji i zapisu.
        return cleaned_value

    def validate(self, attrs):
        # Request znajduje się w kontekście ustawianym automatycznie przez widok DRF.
        request = self.context.get('request')
        # Walidacja duplikatu ma sens tylko dla zalogowanego użytkownika i operacji tworzenia.
        if request and request.user.is_authenticated and self.instance is None:
            # Współrzędne po walidacji pól są obiektami Decimal, zgodnymi z wartościami w bazie.
            latitude = attrs.get('latitude')
            # Długość geograficzną pobieramy z tego samego słownika zwalidowanych pól.
            longitude = attrs.get('longitude')
            # Sprawdzamy punkt niezależnie od nazwy, aby nie zapisać go drugi raz pod inną etykietą.
            duplicate_exists = SavedLocation.objects.filter(
                user=request.user,
                latitude=latitude,
                longitude=longitude,
            ).exists()
            # Czytelny błąd domenowy trafia do frontendu jako odpowiedź HTTP 400.
            if duplicate_exists:
                raise serializers.ValidationError(
                    {'coordinates': 'Ta lokalizacja jest już zapisana na Twoim koncie.'}
                )
        # Zwracamy dane po przejściu walidacji wielopolowej.
        return attrs

    @extend_schema_field(WeatherSnapshotSerializer(allow_null=True))
    def get_latest_weather(self, obj):
        # Widok może wcześniej dołączyć listę jednego najnowszego pomiaru do atrybutu latest_snapshots.
        prefetched_snapshots = getattr(obj, 'latest_snapshots', None)
        # Jeśli prefetch istnieje, nie wykonujemy kolejnego zapytania dla każdej lokalizacji.
        if prefetched_snapshots is not None:
            latest_snapshot = prefetched_snapshots[0] if prefetched_snapshots else None
        else:
            # Fallback obsługuje serializowanie pojedynczego świeżo utworzonego obiektu.
            latest_snapshot = obj.weather_snapshots.order_by('-measured_at').first()
        # Lokalizacja bez historii zwraca null, co frontend może łatwo rozpoznać.
        if latest_snapshot is None:
            return None
        # Ten sam serializer zapewnia spójny format pomiaru na liście i w historii.
        return WeatherSnapshotSerializer(latest_snapshot).data


def saved_locations_queryset(user):
    """Buduje zoptymalizowane zapytanie lokalizacji należących do użytkownika."""

    # Osobny queryset pobiera snapshoty od najnowszego i ogranicza pola do potrzeb odpowiedzi.
    latest_weather_queryset = WeatherSnapshot.objects.order_by('-measured_at')[:1]
    # Prefetch zapisuje pobrane pomiary w pomocniczym atrybucie zamiast zmieniać menedżer relacji.
    latest_weather_prefetch = Prefetch(
        'weather_snapshots',
        queryset=latest_weather_queryset,
        to_attr='latest_snapshots',
    )
    # Każde zapytanie jest obowiązkowo ograniczone do właściciela lokalizacji.
    return SavedLocation.objects.filter(user=user).prefetch_related(latest_weather_prefetch)


class LocationWeatherResponseSerializer(serializers.Serializer):
    """Opisuje odpowiedź endpointu aktualnej pogody zapisanej lokalizacji."""

    location = SavedLocationSerializer(read_only=True)  # Odpowiedź zawiera punkt, którego dotyczy pomiar.
    weather = WeatherSnapshotSerializer(read_only=True)  # Pomiar ma ten sam format co historia.
    cached = serializers.BooleanField(read_only=True)  # Flaga pokazuje, czy uniknięto requestu zewnętrznego.
    cache_ttl_seconds = serializers.IntegerField(read_only=True)  # TTL wyjaśnia strategię cache.


class WeatherHistoryResponseSerializer(serializers.Serializer):
    """Opisuje listę historycznych pomiarów konkretnej lokalizacji."""

    location = SavedLocationSerializer(read_only=True)  # Metadane wskazują właściciela historii.
    results = WeatherSnapshotSerializer(many=True, read_only=True)  # Wyniki są uporządkowane od najnowszych.
    count = serializers.IntegerField(read_only=True)  # Licznik ułatwia frontendowi prezentację pustego stanu.


class EarthquakeEventSerializer(serializers.ModelSerializer):
    """Serializuje zdarzenie sejsmiczne zapisane trwale w bazie."""

    class Meta:
        model = EarthquakeEvent  # Model odpowiada rekordowi zsynchronizowanemu z USGS.
        fields = (
            'id',  # Lokalny klucz umożliwia pobranie szczegółów.
            'external_id',  # Id USGS zapobiega duplikatom i pozostaje przydatne diagnostycznie.
            'title',  # Tytuł opisuje magnitudę i miejsce.
            'magnitude',  # Magnituda steruje filtrowaniem oraz wyglądem markera.
            'depth_km',  # Głębokość umożliwia filtr płytkich zdarzeń.
            'latitude',  # Szerokość jest potrzebna Leafletowi.
            'longitude',  # Długość jest potrzebna Leafletowi.
            'place',  # Tekstowe miejsce jest widoczne w panelu.
            'event_time',  # Czas służy do filtrowania zakresu.
            'source',  # Źródło pozostaje jawne.
            'detail_url',  # Link prowadzi do oficjalnych szczegółów USGS.
            'created_at',  # Czas zapisu pokazuje działanie synchronizacji.
            'updated_at',  # Czas aktualizacji pokazuje idempotentny import.
        )
        read_only_fields = fields  # Zdarzenia powstają wyłącznie przez synchronizację.


class VolcanicEventSerializer(serializers.ModelSerializer):
    """Serializuje wulkan oraz podsumowanie jego erupcji z Smithsonian GVP."""

    class Meta:
        model = VolcanicEvent  # Model przechowuje katalog wulkanów połączony z historią erupcji.
        fields = (
            'id',  # Lokalny klucz służy do endpointu szczegółów.
            'external_id',  # Oficjalny numer GVP gwarantuje idempotencję.
            'title',  # Tytuł pozostaje zgodny z wcześniejszym kontraktem.
            'volcano_name',  # Nazwa wulkanu jest główną etykietą interfejsu.
            'latitude',  # Szerokość punktu na mapie.
            'longitude',  # Długość punktu na mapie.
            'country',  # Kraj pozwala użytkownikowi osadzić marker geograficznie.
            'region',  # Region wspiera filtrowanie.
            'volcano_type',  # Typ opisuje formę geologiczną wulkanu.
            'elevation_m',  # Wysokość jest podawana w metrach.
            'last_eruption_year',  # Osobne pole obsługuje także lata przed naszą erą.
            'vei',  # VEI dotyczy ostatniej znanej erupcji, jeśli źródło je określiło.
            'max_vei',  # Maksymalne znane VEI podsumowuje historię wulkanu.
            'tectonic_setting',  # Ustawienie tektoniczne pochodzi z katalogu GVP.
            'geologic_epoch',  # Epoka geologiczna dokumentuje zakres katalogu.
            'evidence_category',  # Kategoria dowodu mówi, jak potwierdzono aktywność.
            'rock_type',  # Dominujący typ skał jest częścią danych geologicznych.
            'description',  # Dłuższe podsumowanie geologiczne pochodzi ze Smithsonian.
            'event_time',  # Pomocnicza data istnieje tylko dla erupcji mieszczących się w datetime.
            'source',  # Źródło danych jest jawne.
            'detail_url',  # Link prowadzi do materiału pierwotnego.
            'photo_url',  # Zdjęcie jest opcjonalnym materiałem katalogowym.
            'photo_caption',  # Podpis wyjaśnia, co przedstawia zdjęcie.
            'status',  # Status nie jest alertem, lecz informacją o wpisie katalogowym.
            'created_at',  # Czas pierwszego importu.
            'updated_at',  # Czas ostatniego uaktualnienia.
        )
        read_only_fields = fields  # Klient nie tworzy zdarzeń środowiskowych.


class SyncJobSerializer(serializers.ModelSerializer):
    """Serializuje log zadania synchronizacyjnego dla administratora."""

    class Meta:
        model = SyncJob  # Model zapisuje przebieg każdego zadania.
        fields = (
            'id',  # Id pozwala rozróżnić kolejne uruchomienia.
            'job_type',  # Typ wskazuje synchronizowane dane.
            'status',  # Status rozróżnia RUNNING, SUCCESS i FAILED.
            'started_at',  # Czas początku jest podstawą monitorowania.
            'finished_at',  # Czas końca może być pusty dla trwającego zadania.
            'items_fetched',  # Licznik opisuje efekt synchronizacji.
            'error_message',  # Komunikat ułatwia diagnozę niepowodzenia.
            'created_at',  # Techniczny czas utworzenia rekordu.
            'updated_at',  # Czas ostatniej zmiany statusu.
        )
        read_only_fields = fields  # Logi są tworzone wyłącznie przez usługi synchronizacji.


class EnvironmentalListResponseSerializer(serializers.Serializer):
    """Opisuje wspólną obudowę list zdarzeń środowiskowych."""

    results = serializers.ListField(read_only=True)  # Konkretna lista jest opisana serializerem endpointu.
    count = serializers.IntegerField(read_only=True)  # Licznik ułatwia dashboardowi prezentację danych.
    source = serializers.CharField(read_only=True)  # Źródło pokazuje pochodzenie rekordów.


class SyncTaskAcceptedSerializer(serializers.Serializer):
    """Opisuje odpowiedź przyjętego zadania Celery."""

    task_id = serializers.CharField(read_only=True)  # Id Celery pozwala skorelować logi workera.
    job_type = serializers.CharField(read_only=True)  # Typ informuje, którą synchronizację uruchomiono.
    status = serializers.CharField(read_only=True)  # Wartość queued oznacza przyjęcie do kolejki.


class MagnitudeBucketSerializer(serializers.Serializer):
    """Opisuje pojedynczy słupek rozkładu magnitud."""

    label = serializers.CharField(read_only=True)  # Etykieta zawiera czytelny przedział wartości.
    count = serializers.IntegerField(read_only=True)  # Licznik określa wysokość słupka.


class DashboardSyncStateSerializer(serializers.Serializer):
    """Opisuje ostatnie uruchomienie jednego rodzaju synchronizacji."""

    status = serializers.CharField(read_only=True)  # Status może mieć wartość RUNNING, SUCCESS, FAILED albo NEVER.
    started_at = serializers.DateTimeField(read_only=True, allow_null=True)  # Pierwsze uruchomienie może jeszcze nie istnieć.
    finished_at = serializers.DateTimeField(read_only=True, allow_null=True)  # Trwające zadanie nie ma czasu zakończenia.
    items_fetched = serializers.IntegerField(read_only=True)  # Licznik pokazuje efekt zadania.
    error_message = serializers.CharField(read_only=True)  # Błąd jest pusty po sukcesie.


class DashboardLastSyncSerializer(serializers.Serializer):
    """Grupuje stany synchronizacji wszystkich źródeł Dashboardu."""

    earthquakes = DashboardSyncStateSerializer(read_only=True)  # Stan importu USGS.
    weather = DashboardSyncStateSerializer(read_only=True)  # Stan pogody zapisanych punktów.
    volcanoes = DashboardSyncStateSerializer(read_only=True)  # Stan importu katalogu Smithsonian GVP.


class DashboardCacheStateSerializer(serializers.Serializer):
    """Pokazuje, które części odpowiedzi pochodziły z Redisa."""

    global_data = serializers.BooleanField(read_only=True)  # Flaga dotyczy agregacji publicznych.
    user_data = serializers.BooleanField(read_only=True)  # Flaga dotyczy prywatnych lokalizacji.
    ttl_seconds = serializers.IntegerField(read_only=True)  # TTL dokumentuje strategię cache.


class DashboardSummarySerializer(serializers.Serializer):
    """Dokumentuje kompletną odpowiedź endpointu Dashboardu."""

    earthquakes_last_24h = serializers.IntegerField(read_only=True)  # Liczba zdarzeń z ostatniej doby.
    max_magnitude_last_24h = serializers.FloatField(read_only=True, allow_null=True)  # Największa magnituda może nie istnieć.
    range_hours = serializers.IntegerField(read_only=True)  # Zakres wskazuje 24 godziny, 7 dni albo 30 dni.
    volcanic_events = serializers.IntegerField(read_only=True)  # Liczba ostatnich zdarzeń wulkanicznych.
    saved_locations = serializers.IntegerField(read_only=True)  # Prywatny licznik wynosi zero dla użytkownika anonimowego.
    magnitude_distribution = MagnitudeBucketSerializer(many=True, read_only=True)  # Dane wykresu słupkowego.
    latest_earthquakes = EarthquakeEventSerializer(many=True, read_only=True)  # Krótka lista najnowszych zdarzeń.
    locations = SavedLocationSerializer(many=True, read_only=True)  # Pogoda lokalizacji jest widoczna po zalogowaniu.
    last_sync = DashboardLastSyncSerializer(read_only=True)  # Ostatnie synchronizacje wspierają obserwowalność.
    generated_at = serializers.DateTimeField(read_only=True)  # Czas wskazuje moment policzenia agregacji.
    cache = DashboardCacheStateSerializer(read_only=True)  # Metadane pokazują działanie Redisa.
