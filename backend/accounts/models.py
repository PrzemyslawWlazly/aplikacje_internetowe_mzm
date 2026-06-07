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
