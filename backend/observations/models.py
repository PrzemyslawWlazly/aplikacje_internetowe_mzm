"""Modele danych dla lokalizacji, pogody, trzęsień ziemi, wulkanów i synchronizacji."""

from django.conf import settings  # settings pozwala odwołać się do aktualnego modelu użytkownika.
from django.core.validators import MaxValueValidator, MinValueValidator  # Walidatory pilnują zakresów liczbowych.
from django.db import models  # models zawiera klasy pól i modeli Django ORM.


class TimestampedModel(models.Model):
    """Abstrakcyjna baza dodająca znaczniki czasu do modeli domenowych."""

    created_at = models.DateTimeField(auto_now_add=True)  # Czas utworzenia rekordu zapisuje się automatycznie.
    updated_at = models.DateTimeField(auto_now=True)  # Czas ostatniej modyfikacji aktualizuje się automatycznie.

    class Meta:
        abstract = True  # Model bazowy nie tworzy własnej tabeli w bazie danych.


class SavedLocation(TimestampedModel):
    """Lokalizacja zapisana przez użytkownika do obserwacji."""

    user = models.ForeignKey(  # Lokalizacja należy do konkretnego użytkownika.
        settings.AUTH_USER_MODEL,  # Używamy konfigurowalnego modelu użytkownika Django.
        on_delete=models.CASCADE,  # Usunięcie użytkownika usuwa też jego lokalizacje.
        related_name='saved_locations',  # related_name ułatwia pobranie lokalizacji z obiektu użytkownika.
    )
    name = models.CharField(max_length=120)  # Nazwa lokalizacji widoczna w UI.
    latitude = models.DecimalField(  # Szerokość geograficzna punktu.
        max_digits=9,  # Zakres pozwala zapisać wartości z sześcioma miejscami po przecinku.
        decimal_places=6,  # Dokładność wystarcza dla mapy miejskiej.
        validators=[MinValueValidator(-90), MaxValueValidator(90)],  # Szerokość musi mieścić się od -90 do 90.
    )
    longitude = models.DecimalField(  # Długość geograficzna punktu.
        max_digits=9,  # Zakres pozwala zapisać wartości od -180 do 180.
        decimal_places=6,  # Dokładność jest spójna z latitude.
        validators=[MinValueValidator(-180), MaxValueValidator(180)],  # Długość musi mieścić się od -180 do 180.
    )
    country = models.CharField(max_length=100, blank=True)  # Kraj jest opcjonalnym opisem lokalizacji.
    region = models.CharField(max_length=120, blank=True)  # Region pomaga grupować punkty.
    description = models.TextField(blank=True)  # Opis użytkownika jest opcjonalny.

    class Meta:
        ordering = ['name']  # Domyślnie sortujemy lokalizacje alfabetycznie.
        constraints = [  # Ograniczenia pilnują spójności na poziomie bazy.
            models.UniqueConstraint(  # Jeden użytkownik nie powinien zapisać tych samych współrzędnych dwa razy.
                fields=['user', 'latitude', 'longitude'],  # Nazwa może się zmienić, ale punkt geograficzny pozostaje ten sam.
                name='unique_saved_coordinates_per_user',  # Nazwa ograniczenia opisuje rzeczywistą regułę biznesową.
            )
        ]

    def __str__(self):
        return f'{self.name} ({self.latitude}, {self.longitude})'  # Czytelny opis w panelu admina.


class WeatherSnapshot(TimestampedModel):
    """Pojedynczy zapis pogody dla obserwowanej lokalizacji."""

    location = models.ForeignKey(  # Snapshot pogody należy do zapisanej lokalizacji.
        SavedLocation,  # Łączymy pomiar z lokalizacją użytkownika.
        on_delete=models.CASCADE,  # Usunięcie lokalizacji usuwa jej historię pogody.
        related_name='weather_snapshots',  # Pozwala pobrać historię przez location.weather_snapshots.
    )
    temperature = models.DecimalField(max_digits=5, decimal_places=2)  # Temperatura w stopniach Celsjusza.
    humidity = models.PositiveSmallIntegerField(  # Wilgotność jest liczbą całkowitą od 0 do 100.
        validators=[MinValueValidator(0), MaxValueValidator(100)]  # Walidator pilnuje poprawnego procentu.
    )
    pressure = models.PositiveSmallIntegerField()  # Ciśnienie atmosferyczne zapisujemy jako dodatnią liczbę.
    wind_speed = models.DecimalField(max_digits=6, decimal_places=2)  # Prędkość wiatru może mieć część dziesiętną.
    cloud_cover = models.PositiveSmallIntegerField(  # Zachmurzenie zapisujemy jako procent nieba pokrytego chmurami.
        null=True,  # Starsze rekordy i źródła bez tej wartości pozostają poprawne.
        blank=True,  # Pole nie musi być uzupełniane ręcznie w panelu administracyjnym.
        validators=[MinValueValidator(0), MaxValueValidator(100)],  # Procent musi mieścić się od 0 do 100.
    )
    weather_code = models.PositiveSmallIntegerField(  # Kod WMO pozwala odtworzyć opis warunków pogodowych.
        null=True,  # Nie każde źródło musi udostępniać kod.
        blank=True,  # Brak kodu nie blokuje zapisania pozostałych parametrów.
    )
    description = models.CharField(max_length=255, blank=True)  # Tekstowy opis pogody jest opcjonalny.
    source = models.CharField(max_length=80)  # Źródło danych, np. Open-Meteo.
    measured_at = models.DateTimeField()  # Czas faktycznego pomiaru z API zewnętrznego.

    class Meta:
        ordering = ['-measured_at']  # Najnowsze pomiary pokazujemy jako pierwsze.
        constraints = [  # Ograniczenie na poziomie bazy chroni historię również przy równoległych workerach.
            models.UniqueConstraint(  # Ten sam pomiar źródłowy może wystąpić tylko raz dla danej lokalizacji.
                fields=['location', 'source', 'measured_at'],  # Czas i źródło jednoznacznie opisują snapshot punktu.
                name='unique_weather_measurement_per_location',  # Nazwa pojawi się w migracji i diagnostyce bazy.
            )
        ]
        indexes = [  # Indeksy przyspieszają typowe zapytania.
            models.Index(fields=['location', '-measured_at']),  # Historia lokalizacji będzie filtrowana po czasie.
        ]

    def __str__(self):
        return f'{self.location.name}: {self.temperature} C at {self.measured_at:%Y-%m-%d %H:%M}'  # Opis adminowy.


class EarthquakeEvent(TimestampedModel):
    """Zdarzenie sejsmiczne pobrane z zewnętrznego źródła."""

    external_id = models.CharField(max_length=120, unique=True)  # Identyfikator z API zapobiega duplikatom.
    title = models.CharField(max_length=255)  # Tytuł zdarzenia do listy i szczegółów.
    magnitude = models.DecimalField(  # Magnituda jest kluczowym parametrem filtrowania.
        max_digits=4,  # Zakres wystarcza dla wartości typu 6.4 lub 10.0.
        decimal_places=1,  # Jedno miejsce po przecinku jest wystarczające dla UI.
        validators=[MinValueValidator(0)],  # Magnituda nie powinna być ujemna w naszym modelu.
    )
    depth_km = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)  # Głębokość może być nieznana.
    latitude = models.DecimalField(  # Szerokość punktu zdarzenia.
        max_digits=9,  # Zakres geograficzny z sześcioma miejscami po przecinku.
        decimal_places=6,  # Dokładność zgodna z mapą.
        validators=[MinValueValidator(-90), MaxValueValidator(90)],  # Walidacja zakresu geograficznego.
    )
    longitude = models.DecimalField(  # Długość punktu zdarzenia.
        max_digits=9,  # Zakres obejmuje cały świat.
        decimal_places=6,  # Dokładność zgodna z latitude.
        validators=[MinValueValidator(-180), MaxValueValidator(180)],  # Walidacja zakresu geograficznego.
    )
    place = models.CharField(max_length=255, blank=True)  # Opis lokalizacji z API, np. "near Honshu".
    event_time = models.DateTimeField()  # Czas wystąpienia trzęsienia ziemi.
    source = models.CharField(max_length=80)  # Źródło danych, np. USGS.
    detail_url = models.URLField(blank=True)  # Link do szczegółów w zewnętrznym serwisie.

    class Meta:
        ordering = ['-event_time']  # Najnowsze trzęsienia pokazujemy jako pierwsze.
        indexes = [  # Indeksy wspierają filtrowanie po czasie i magnitudzie.
            models.Index(fields=['-event_time']),  # Dashboard i lista często pytają o najnowsze zdarzenia.
            models.Index(fields=['magnitude']),  # Filtr minimalnej magnitudy wymaga szybkiego wyszukiwania.
        ]

    def __str__(self):
        return f'M{self.magnitude} - {self.place or self.title}'  # Format znany z opisów sejsmicznych.


class VolcanicEvent(TimestampedModel):
    """Wulkan z oficjalnego katalogu Smithsonian Global Volcanism Program."""

    external_id = models.CharField(max_length=120, unique=True)  # Numer GVP jednoznacznie identyfikuje wulkan.
    title = models.CharField(max_length=255)  # Tytuł pozostaje dla zgodności ze starszym kontraktem API.
    volcano_name = models.CharField(max_length=160, blank=True)  # Oficjalna podstawowa nazwa pochodzi z katalogu GVP.
    latitude = models.DecimalField(  # Szerokość geograficzna środka wulkanu.
        max_digits=9,  # Zakres pozwala zapisać cały świat.
        decimal_places=6,  # Dokładność jest wystarczająca dla markerów mapy.
        validators=[MinValueValidator(-90), MaxValueValidator(90)],  # Walidacja poprawnej szerokości.
    )
    longitude = models.DecimalField(  # Długość geograficzna środka wulkanu.
        max_digits=9,  # Zakres pozwala zapisać cały świat.
        decimal_places=6,  # Dokładność jest spójna z latitude.
        validators=[MinValueValidator(-180), MaxValueValidator(180)],  # Walidacja poprawnej długości.
    )
    country = models.CharField(max_length=120, blank=True)  # Kraj ułatwia filtrowanie pełnego katalogu.
    region = models.CharField(max_length=160, blank=True)  # Region wulkaniczny pochodzi z klasyfikacji Smithsonian.
    volcano_type = models.CharField(max_length=120, blank=True)  # Typ opisuje morfologię, np. stratowulkan lub kaldera.
    elevation_m = models.IntegerField(null=True, blank=True)  # Wysokość może być ujemna dla obiektów podmorskich.
    last_eruption_year = models.IntegerField(null=True, blank=True)  # Rok może być ujemny dla erupcji przed naszą erą.
    vei = models.PositiveSmallIntegerField(  # VEI ostatniej znanej erupcji nie jest cechą stałą samego wulkanu.
        null=True,  # Nie każdej erupcji udało się przypisać indeks.
        blank=True,  # Brak wartości jest informacją naukową, a nie błędem importu.
        validators=[MinValueValidator(0), MaxValueValidator(8)],  # Klasyczny zakres VEI wynosi od 0 do 8.
    )
    max_vei = models.PositiveSmallIntegerField(  # Najwyższe znane VEI podsumowuje historię erupcyjną wulkanu.
        null=True,  # Wulkan bez sklasyfikowanej erupcji pozostaje widoczny na mapie.
        blank=True,  # Pole jest opcjonalne również w panelu Django.
        validators=[MinValueValidator(0), MaxValueValidator(8)],  # Chronimy bazę przed błędną wartością źródłową.
    )
    tectonic_setting = models.CharField(max_length=180, blank=True)  # Ustawienie tektoniczne wyjaśnia genezę wulkanu.
    geologic_epoch = models.CharField(max_length=80, blank=True)  # Epoka odróżnia katalog holoceński od innych danych.
    evidence_category = models.CharField(max_length=120, blank=True)  # Pole opisuje dowód włączenia do katalogu.
    rock_type = models.CharField(max_length=160, blank=True)  # Dominujący typ skał daje podstawowy kontekst geologiczny.
    description = models.TextField(blank=True)  # Smithsonian udostępnia rozbudowane podsumowanie geologiczne.
    event_time = models.DateTimeField(null=True, blank=True)  # Dla erupcji BCE używamy osobnego pola roku.
    source = models.CharField(max_length=80)  # Źródłem katalogu jest Smithsonian GVP.
    detail_url = models.URLField(max_length=500, blank=True)  # Link prowadzi do oficjalnej karty wulkanu.
    photo_url = models.URLField(max_length=500, blank=True)  # Opcjonalne zdjęcie pochodzi z galerii Smithsonian.
    photo_caption = models.TextField(blank=True)  # Podpis zdjęcia zachowuje kontekst źródłowy.
    status = models.CharField(max_length=80, blank=True)  # Status „catalogued” odróżnia katalog od aktywnego alarmu.

    class Meta:
        ordering = ['volcano_name']  # Pełny katalog najłatwiej przeglądać alfabetycznie.
        indexes = [  # Indeksy wspierają listę i filtrowanie.
            models.Index(fields=['volcano_name']),  # Przyspiesza alfabetyczną listę wszystkich wulkanów.
            models.Index(fields=['country']),  # Filtr kraju jest naturalny przy globalnym katalogu.
            models.Index(fields=['region']),  # Przyspiesza filtrowanie po regionie.
            models.Index(fields=['max_vei']),  # Indeks wspiera wybór wulkanów o znanych silnych erupcjach.
        ]

    def __str__(self):
        return self.volcano_name or self.title  # W adminie preferujemy nazwę wulkanu, jeśli istnieje.


class SyncJob(TimestampedModel):
    """Log pojedynczej synchronizacji danych z zewnętrznym API."""

    class JobType(models.TextChoices):
        WEATHER = 'WEATHER_SYNC', 'Weather sync'  # Synchronizacja danych pogodowych.
        EARTHQUAKE = 'EARTHQUAKE_SYNC', 'Earthquake sync'  # Synchronizacja danych sejsmicznych.
        VOLCANO = 'VOLCANO_SYNC', 'Volcano sync'  # Synchronizacja danych wulkanicznych.

    class Status(models.TextChoices):
        RUNNING = 'RUNNING', 'Running'  # Zadanie nadal trwa.
        SUCCESS = 'SUCCESS', 'Success'  # Zadanie zakończyło się sukcesem.
        FAILED = 'FAILED', 'Failed'  # Zadanie zakończyło się błędem.

    job_type = models.CharField(max_length=40, choices=JobType.choices)  # Typ mówi, co synchronizowaliśmy.
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)  # Aktualny wynik zadania.
    started_at = models.DateTimeField()  # Czas startu synchronizacji.
    finished_at = models.DateTimeField(null=True, blank=True)  # Czas końca jest pusty, dopóki zadanie trwa.
    items_fetched = models.PositiveIntegerField(default=0)  # Liczba pobranych elementów pomaga w panelu admina.
    error_message = models.TextField(blank=True)  # Treść błędu jest zapisywana tylko przy niepowodzeniu.

    class Meta:
        ordering = ['-started_at']  # Najnowsze synchronizacje pokazujemy na górze.
        indexes = [  # Indeksy pomagają panelowi statusu synchronizacji.
            models.Index(fields=['job_type', '-started_at']),  # Szybko znajdujemy ostatnie zadanie danego typu.
            models.Index(fields=['status']),  # Możemy szybko filtrować błędy i zadania trwające.
        ]

    def __str__(self):
        return f'{self.job_type} - {self.status}'  # Czytelny opis zadania w adminie.
