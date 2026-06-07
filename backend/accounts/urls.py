from django.urls import path  # Funkcja path łączy adres URL z klasą widoku.
from rest_framework_simplejwt.views import TokenRefreshView  # Gotowy widok wymienia refresh token na access token.

from .views import CurrentUserView, GoogleLoginView  # Importujemy endpoint logowania oraz bieżącego profilu.


app_name = 'accounts'  # Przestrzeń nazw zapobiega kolizjom nazw tras z innymi aplikacjami.

urlpatterns = [
    path('google/', GoogleLoginView.as_view(), name='google-login'),  # Logowanie tokenem ID od Google.
    path('me/', CurrentUserView.as_view(), name='current-user'),  # Odczyt profilu na podstawie lokalnego JWT.
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),  # Odświeżenie wygasającego access tokenu.
]
