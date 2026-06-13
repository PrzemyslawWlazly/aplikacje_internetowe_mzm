"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin  # Admin Django pozwala podejrzeć dane zapisane w bazie.
from django.urls import include, path  # include podpina adresy z aplikacji, a path definiuje pojedynczą trasę.
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView  # Widoki generują dokumentację OpenAPI.

from core.views import health  # Healthcheck sprawdza bazę i Redis przed startem zależnych usług.

urlpatterns = [  # Główna lista tras całego backendu.
    path('admin/', admin.site.urls),  # Panel administracyjny Django.
    path('api/auth/', include('accounts.urls')),  # Logowanie Google, profil i odświeżanie lokalnego JWT.
    path('api/', include('observations.urls')),  # Publiczne endpointy danych środowiskowych.
    path('api/health/', health, name='health'),  # Publiczny stan backendu, PostgreSQL i Redisa.
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),  # Surowy schemat OpenAPI w JSON/YAML.
    path(
        'api/docs/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),  # Interaktywna dokumentacja Swagger UI.
]
