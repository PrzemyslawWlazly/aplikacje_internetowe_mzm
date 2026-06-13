from django.conf import settings  # Pobieramy aktywny model użytkownika skonfigurowany w Django.
from django.db import models  # Importujemy klasy potrzebne do opisania tabeli bazy danych.


class GoogleAccount(models.Model):
    """Przechowuje trwałe powiązanie użytkownika aplikacji z kontem Google."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,  # Relacja działa także po ewentualnej zmianie modelu użytkownika.
        on_delete=models.CASCADE,  # Usunięcie użytkownika usuwa również jego powiązanie z Google.
        related_name='google_account',  # Pozwala użyć zapisu user.google_account.
    )
    subject = models.CharField(
        max_length=255,  # Identyfikator Google zwykle jest krótszy, ale zostawiamy bezpieczny zapas.
        unique=True,  # Jedno konto Google może być połączone tylko z jednym użytkownikiem.
        help_text='Stabilny identyfikator użytkownika z pola sub tokenu Google.',
    )
    email = models.EmailField(
        help_text='Zweryfikowany adres e-mail otrzymany w tokenie Google.',
    )
    picture_url = models.URLField(
        blank=True,  # Zdjęcie profilowe nie jest wymagane przez Google.
        max_length=500,  # Adresy zdjęć z serwisów Google bywają dłuższe niż domyślne 200 znaków.
        help_text='Opcjonalny adres zdjęcia profilowego użytkownika.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,  # Django zapisuje moment utworzenia powiązania.
    )
    updated_at = models.DateTimeField(
        auto_now=True,  # Pole aktualizuje się przy każdym zapisie rekordu.
    )

    class Meta:
        ordering = ('-created_at',)  # Najnowsze połączenia będą pierwsze w panelu administracyjnym.
        verbose_name = 'konto Google'  # Polska nazwa pojedynczego rekordu w panelu admina.
        verbose_name_plural = 'konta Google'  # Polska nazwa listy rekordów w panelu admina.

    def __str__(self):
        # Czytelny opis ułatwia rozpoznanie rekordu podczas pracy w panelu Django.
        return f'{self.email} ({self.subject})'


class UserPreference(models.Model):
    """Przechowuje proste ustawienia interfejsu należące do jednego użytkownika."""

    class DashboardRange(models.IntegerChoices):
        """Dozwolone zakresy czasu są ograniczone do opcji opisanych w specyfikacji."""

        DAY = 24, '24 godziny'  # Krótki zakres pokazuje najświeższe zdarzenia.
        WEEK = 168, '7 dni'  # Tydzień daje szerszy obraz aktywności sejsmicznej.
        MONTH = 720, '30 dni'  # Miesiąc odpowiada maksymalnemu zakresowi publicznego API.

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,  # Preferencje należą do aktywnego modelu użytkownika Django.
        on_delete=models.CASCADE,  # Usunięcie konta usuwa również jego ustawienia.
        related_name='preferences',  # Relacja pozwala użyć zapisu user.preferences.
    )
    dashboard_range_hours = models.PositiveSmallIntegerField(
        choices=DashboardRange.choices,  # Baza i serializer przyjmują tylko trzy świadomie wybrane wartości.
        default=DashboardRange.DAY,  # Nowe konto zaczyna od najczęściej używanego zakresu 24 godzin.
    )
    created_at = models.DateTimeField(auto_now_add=True)  # Czas utworzenia pomaga pokazać trwałość rekordu.
    updated_at = models.DateTimeField(auto_now=True)  # Zmiana zakresu aktualizuje znacznik automatycznie.

    class Meta:
        verbose_name = 'preferencje użytkownika'  # Polska nazwa jest widoczna w panelu Django.
        verbose_name_plural = 'preferencje użytkowników'  # Liczba mnoga opisuje tabelę administracyjną.

    def __str__(self):
        # Opis łączy właściciela z aktualnie wybranym zakresem.
        return f'{self.user}: {self.dashboard_range_hours} h'
