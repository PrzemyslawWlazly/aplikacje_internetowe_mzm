// Bazowy adres backendu można zmienić osobno dla środowiska lokalnego, Dockera i produkcji.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'

// Client ID jest publicznym identyfikatorem aplikacji utworzonym w Google Cloud Console.
export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ''
