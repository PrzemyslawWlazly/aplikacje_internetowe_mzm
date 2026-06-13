// Axios wykonuje request podsumowania Dashboardu do backendu Django.
import axios from 'axios'

// Wspólny adres API zapewnia zgodność z pozostałymi modułami aplikacji.
import { API_BASE_URL } from '../config'

// Funkcja pobiera publiczne agregacje i opcjonalną część prywatną zalogowanego użytkownika.
export async function fetchDashboardSummary(accessToken = '') {
  // Token jest dołączany tylko wtedy, gdy w aplikacji istnieje aktywna sesja.
  const config = accessToken
    ? { headers: { Authorization: `Bearer ${accessToken}` } }
    : {}
  // Jeden endpoint ogranicza liczbę requestów wykonywanych podczas wejścia na Dashboard.
  const response = await axios.get(`${API_BASE_URL}/dashboard/summary/`, config)
  // Komponent otrzymuje gotowe statystyki, listy i metadane cache.
  return response.data
}

// Funkcja zapisuje domyślny zakres Dashboardu w relacyjnej bazie użytkownika.
export async function updateDashboardPreference(accessToken, dashboardRangeHours) {
  // PATCH zmienia tylko jedno ustawienie bez nadpisywania przyszłych preferencji.
  const response = await axios.patch(
    `${API_BASE_URL}/auth/preferences/`,
    { dashboard_range_hours: dashboardRangeHours },
    { headers: { Authorization: `Bearer ${accessToken}` } },
  )
  // Zwracamy rekord potwierdzony przez serializer backendu.
  return response.data
}
