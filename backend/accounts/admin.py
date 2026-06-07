from django.contrib import admin  # Importujemy mechanizm panelu administracyjnego Django.

from .models import GoogleAccount  # Importujemy model, który chcemy oglądać w panelu admina.


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
