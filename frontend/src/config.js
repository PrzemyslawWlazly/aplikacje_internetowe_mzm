// Odczytujemy adres ustawiony przez Vite albo używamy lokalnego backendu deweloperskiego.
const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'

// Usuwamy końcowy ukośnik, aby moduły nie tworzyły adresów z podwójnym separatorem.
const normalizedApiBaseUrl = configuredApiBaseUrl.replace(/\/+$/, '')

// Dopisujemy prefiks tras Django, jeśli konfiguracja zawierała wyłącznie host i port.
export const API_BASE_URL = normalizedApiBaseUrl.endsWith('/api')
  ? normalizedApiBaseUrl
  : `${normalizedApiBaseUrl}/api`

// Client ID jest publicznym identyfikatorem aplikacji utworzonym w Google Cloud Console.
export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ''
