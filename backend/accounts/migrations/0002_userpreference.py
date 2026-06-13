# Migracja została przygotowana dla modelu trwałych preferencji użytkownika.
import django.db.models.deletion  # Moduł opisuje zachowanie relacji po usunięciu użytkownika.
from django.conf import settings  # Ustawienia wskazują aktualny model użytkownika.
from django.db import migrations, models  # Klasy migracji tworzą tabelę i jej pola.


class Migration(migrations.Migration):
    """Tworzy relację jeden do jednego między użytkownikiem i preferencjami."""

    dependencies = [
        ('accounts', '0001_initial'),  # Nowa tabela zależy od wcześniejszego modelu GoogleAccount.
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),  # Relacja respektuje konfigurowalny model użytkownika.
    ]

    operations = [
        migrations.CreateModel(
            name='UserPreference',  # Nazwa odpowiada modelowi z aplikacji accounts.
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),  # Klucz główny.
                (
                    'dashboard_range_hours',
                    models.PositiveSmallIntegerField(
                        choices=[(24, '24 godziny'), (168, '7 dni'), (720, '30 dni')],
                        default=24,
                    ),
                ),  # Pole ogranicza preferencję do trzech wartości.
                ('created_at', models.DateTimeField(auto_now_add=True)),  # Czas pierwszego zapisu.
                ('updated_at', models.DateTimeField(auto_now=True)),  # Czas ostatniej zmiany.
                (
                    'user',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='preferences',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),  # Każdy użytkownik ma maksymalnie jeden rekord ustawień.
            ],
            options={
                'verbose_name': 'preferencje użytkownika',  # Polska nazwa pojedyncza.
                'verbose_name_plural': 'preferencje użytkowników',  # Polska nazwa mnoga.
            },
        ),
    ]
