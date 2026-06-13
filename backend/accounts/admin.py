from django.contrib import admin  # Importujemy mechanizm panelu administracyjnego Django.

from .models import GoogleAccount, UserPreference  # Importujemy konto Google i preferencje użytkownika.


@admin.register(GoogleAccount)
class GoogleAccountAdmin(admin.ModelAdmin):
    """Konfiguruje tabelę kont Google w panelu administracyjnym."""

    list_display = (
        'email',  # Pokazujemy zweryfikowany adres e-mail.
        'user',  # Pokazujemy powiązanego użytkownika Django.
        'subject',  # Pokazujemy stabilny identyfikator konta Google.
        'created_at',  # Pokazujemy moment pierwszego logowania.
    )
    search_fields = (
        'email',  # Administrator może wyszukiwać po adresie e-mail.
        'subject',  # Administrator może wyszukiwać po identyfikatorze Google.
        'user__username',  # Administrator może wyszukiwać po nazwie użytkownika Django.
    )
    readonly_fields = (
        'created_at',  # Data utworzenia jest wyliczana automatycznie.
        'updated_at',  # Data aktualizacji jest wyliczana automatycznie.
    )


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    """Pokazuje zakres Dashboardu zapisany dla każdego użytkownika."""

    list_display = ('user', 'dashboard_range_hours', 'updated_at')  # Lista prezentuje właściciela i aktualną wartość.
    list_filter = ('dashboard_range_hours',)  # Filtr pozwala szybko porównać używane zakresy.
    search_fields = ('user__username', 'user__email')  # Wyszukiwanie działa po technicznej nazwie i e-mailu.
