// Axios wykonuje chronione requesty administracyjne.
import axios from 'axios'

// Wspólny adres API zachowuje zgodność z pozostałymi modułami.
import { API_BASE_URL } from '../config'

// Helper buduje nagłówek JWT administratora.
function authorizationConfig(accessToken) {
  // Token nie trafia do adresu ani treści requestu.
  return { headers: { Authorization: `Bearer ${accessToken}` } }
}

// Funkcja pobiera ostatnie logi wszystkich rodzajów synchronizacji.
export async function fetchSyncStatus(accessToken) {
  // Endpoint IsAdminUser zwróci 403 dla zwykłego konta.
  const response = await axios.get(
    `${API_BASE_URL}/admin/sync/status/`,
    authorizationConfig(accessToken),
  )
  // Odpowiedź zawiera listę oraz licznik logów SyncJob.
  return response.data
}

// Funkcja dodaje wybrany typ synchronizacji do kolejki Celery.
export async function startSynchronization(accessToken, jobType) {
  // Typ jest wybierany z białej listy interfejsu i backendu.
  const response = await axios.post(
    `${API_BASE_URL}/admin/sync/${jobType}/`,
    {},
    authorizationConfig(accessToken),
  )
  // Kod 202 zawiera id zadania przekazanego do brokera Redis.
  return response.data
}
