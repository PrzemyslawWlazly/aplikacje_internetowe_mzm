from rest_framework import serializers  # Serializery walidują dane wejściowe i budują odpowiedzi JSON.

from .models import UserPreference  # Model przechowuje trwały zakres Dashboardu użytkownika.


class UserPreferenceSerializer(serializers.ModelSerializer):
    """Waliduje i zwraca proste ustawienia zalogowanego użytkownika."""

    class Meta:
        model = UserPreference  # Serializer zapisuje rekord powiązany relacją jeden do jednego.
        fields = (
            'dashboard_range_hours',  # Frontend używa wartości 24, 168 albo 720 godzin.
            'updated_at',  # Czas zmiany pokazuje, że ustawienie zostało utrwalone.
        )
        read_only_fields = ('updated_at',)  # Znacznik czasu jest zarządzany wyłącznie przez Django.


class GoogleCredentialSerializer(serializers.Serializer):
    """Sprawdza kształt danych przesyłanych po zalogowaniu w oknie Google."""

    credential = serializers.CharField(
        allow_blank=False,  # Pusty token nie może zostać przekazany do weryfikacji.
        trim_whitespace=True,  # Usuwamy przypadkowe spacje z początku i końca wartości.
        help_text='Token ID otrzymany z Google Identity Services.',
    )


class AuthenticatedUserSerializer(serializers.Serializer):
    """Opisuje publiczne dane zalogowanego użytkownika zwracane frontendowi."""

    id = serializers.IntegerField(read_only=True)  # Wewnętrzny identyfikator użytkownika Django.
    email = serializers.EmailField(read_only=True)  # Zweryfikowany adres e-mail konta Google.
    first_name = serializers.CharField(read_only=True)  # Imię pobrane z profilu Google.
    last_name = serializers.CharField(read_only=True)  # Nazwisko pobrane z profilu Google.
    picture_url = serializers.URLField(read_only=True)  # Adres opcjonalnego zdjęcia profilowego.
    is_staff = serializers.BooleanField(read_only=True)  # Flaga pozwala pokazać panel synchronizacji administratorowi.
    preferences = UserPreferenceSerializer(read_only=True)  # Profil zawiera trwały domyślny zakres danych.


class GoogleLoginResponseSerializer(serializers.Serializer):
    """Opisuje odpowiedź po poprawnej wymianie tokenu Google."""

    access = serializers.CharField(read_only=True)  # Krótko żyjący token JWT do requestów API.
    refresh = serializers.CharField(read_only=True)  # Dłużej żyjący token do odświeżania sesji.
    user = AuthenticatedUserSerializer(read_only=True)  # Profil pozwala od razu zaktualizować frontend.


class CurrentUserResponseSerializer(serializers.Serializer):
    """Opisuje odpowiedź endpointu zwracającego bieżący profil."""

    user = AuthenticatedUserSerializer(read_only=True)  # Profil wynika z użytkownika zapisanego w access tokenie.
