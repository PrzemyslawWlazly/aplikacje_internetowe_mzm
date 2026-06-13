// Hooki Reacta przechowują dane odpowiedzi i ponawiają request po zmianie konta.
import { useCallback, useEffect, useState } from 'react'
// Recharts rysuje rozkład magnitud wyliczony przez backend.
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

// Funkcja API zna wspólny adres backendu oraz opcjonalny nagłówek JWT.
import { fetchDashboardSummary, updateDashboardPreference } from './api'

// Stałe tłumaczą techniczne typy synchronizacji na język interfejsu.
const SYNC_LABELS = {
  earthquakes: 'Trzęsienia ziemi', // Dane sejsmiczne pochodzą z USGS.
  weather: 'Pogoda lokalizacji', // Pomiary zapisanych punktów pochodzą z Open-Meteo.
  volcanoes: 'Katalog wulkanów', // Katalog wulkanów pochodzi ze Smithsonian GVP.
}

// Stałe tłumaczą statusy modelu SyncJob na krótkie polskie komunikaty.
const STATUS_LABELS = {
  SUCCESS: 'Zakończono', // Zadanie poprawnie zapisało dane.
  FAILED: 'Błąd', // Zadanie zakończyło się błędem.
  RUNNING: 'W toku', // Worker nadal przetwarza dane.
  NEVER: 'Nie uruchamiano', // W bazie nie ma jeszcze logu danego typu.
}

// Funkcja wydobywa czytelny komunikat z odpowiedzi DRF albo błędu sieci.
function requestErrorMessage(error) {
  // Standardowe pole detail ma pierwszeństwo przed technicznym komunikatem Axios.
  return error.response?.data?.detail ?? error.message ?? 'Nie udało się pobrać Dashboardu.'
}

// Funkcja formatuje czas zgodnie z polskimi ustawieniami przeglądarki.
function formatDateTime(value) {
  // Brak czasu oznacza, że synchronizacja jeszcze się nie odbyła.
  if (!value) return '-'
  // Krótki format pozostaje czytelny w kompaktowych wierszach.
  return new Date(value).toLocaleString('pl-PL', {
    dateStyle: 'short',
    timeStyle: 'short',
  })
}

// Funkcja przedstawia magnitudę zawsze z jedną cyfrą po przecinku.
function formatMagnitude(value) {
  // Brak zdarzeń w ostatniej dobie pokazujemy neutralną kreską.
  if (value == null) return '-'
  // Number normalizuje również wartości tekstowe zwracane przez DecimalField.
  return Number(value).toFixed(1)
}

// Komponent renderuje ekran analityczny zgodny z zakresem projektu.
function DashboardView({
  authSession,
  onOpenLogin,
  onShowEarthquake,
  onShowLocations,
  onUpdateUser,
  requestWithAuth,
}) {
  // Dane zawierają część globalną oraz prywatne lokalizacje bieżącego konta.
  const [dashboard, setDashboard] = useState(null)
  // Loading stabilizuje układ podczas pierwszego requestu i ręcznego odświeżenia.
  const [loading, setLoading] = useState(true)
  // Błąd jest lokalny dla Dashboardu i nie zasłania pozostałych modułów.
  const [error, setError] = useState('')
  // Licznik pozwala ponowić efekt bez przeładowania całej strony.
  const [refreshVersion, setRefreshVersion] = useState(0)
  // Zapis preferencji ma osobny stan, aby nie blokował całego Dashboardu.
  const [preferenceSaving, setPreferenceSaving] = useState(false)

  // Id konta jest prostą i stabilną zależnością pobierania prywatnych danych.
  const authenticatedUserId = authSession?.user?.id

  // Callback zwiększa wersję requestu po kliknięciu przycisku odświeżania.
  const refreshDashboard = useCallback(() => {
    // React uruchomi efekt ponownie po zmianie licznika.
    setRefreshVersion((currentVersion) => currentVersion + 1)
  }, [])

  // Efekt pobiera podsumowanie po wejściu, zalogowaniu, wylogowaniu lub ręcznym odświeżeniu.
  useEffect(() => {
    // Flaga chroni stan przed spóźnioną odpowiedzią poprzedniego requestu.
    let active = true

    // Funkcja asynchroniczna porządkuje publiczny i uwierzytelniony wariant requestu.
    async function loadDashboard() {
      // Czyścimy poprzedni komunikat przed ponowną próbą.
      setError('')
      // Pokazujemy stan pobierania w pasku narzędzi.
      setLoading(true)

      try {
        // Zalogowana osoba korzysta ze wspólnego mechanizmu odnawiania JWT.
        const data = authenticatedUserId
          ? await requestWithAuth(fetchDashboardSummary)
          : await fetchDashboardSummary()
        // Aktualizujemy ekran tylko wtedy, gdy efekt nadal jest aktywny.
        if (active) setDashboard(data)
      } catch (requestError) {
        // Zachowujemy poprzednie dane, ale pokazujemy błąd ostatniej próby.
        if (active) setError(requestErrorMessage(requestError))
      } finally {
        // Kończymy loading wyłącznie dla aktualnego efektu.
        if (active) setLoading(false)
      }
    }

    // Uruchamiamy request po przygotowaniu funkcji.
    loadDashboard()

    // Cleanup ignoruje odpowiedź po zmianie użytkownika albo opuszczeniu widoku.
    return () => {
      active = false
    }
  }, [authenticatedUserId, refreshVersion, requestWithAuth])

  // Podczas pierwszego pobrania pokazujemy stabilny, prosty stan pusty.
  if (!dashboard && loading) {
    return <p className="dashboard-state">Pobieranie podsumowania...</p>
  }

  // Całkowity brak danych po błędzie daje czytelną akcję ponowienia.
  if (!dashboard) {
    return (
      <section className="dashboard-state dashboard-state-error">
        <strong>Nie udało się wczytać Dashboardu.</strong>
        <span>{error}</span>
        <button onClick={refreshDashboard} type="button">Spróbuj ponownie</button>
      </section>
    )
  }

  // Karty są budowane z jednego zestawu danych zwróconego przez backend.
  const statistics = [
    { label: `Trzęsienia / ${dashboard.range_hours} h`, value: dashboard.earthquakes_last_24h }, // Licznik wybranego zakresu.
    { label: `Największa M / ${dashboard.range_hours} h`, value: formatMagnitude(dashboard.max_magnitude_last_24h) }, // Maksimum zakresu.
    { label: 'Wulkany holoceńskie', value: dashboard.volcanic_events }, // Licznik obejmuje pełny katalog Smithsonian.
    { label: 'Zapisane lokalizacje', value: dashboard.saved_locations }, // Licznik prywatny albo zero.
    { label: 'Cache Dashboardu', value: `${Math.round(dashboard.cache.ttl_seconds / 60)} min` }, // Konfiguracja Redis.
  ]

  // Funkcja zapisuje preferencję i ponownie pobiera agregacje dla nowego okresu.
  async function changeDashboardRange(rangeHours) {
    // Niezalogowany użytkownik nie ma prywatnego rekordu ustawień.
    if (!authSession) {
      onOpenLogin()
      return
    }
    // Czyścimy poprzedni błąd przed zapisem.
    setError('')
    // Blokujemy kontrolkę na czas requestu PATCH.
    setPreferenceSaving(true)

    try {
      // Wrapper odnowi JWT, jeśli access token wygasł.
      const preferences = await requestWithAuth(
        (accessToken) => updateDashboardPreference(accessToken, rangeHours),
      )
      // Rodzic aktualizuje profil przechowywany w sesji i localStorage.
      onUpdateUser({
        ...authSession.user,
        preferences,
      })
      // Dashboard po zmianie pobierze cache odpowiadający nowemu zakresowi.
      setRefreshVersion((currentVersion) => currentVersion + 1)
    } catch (requestError) {
      // Błąd walidacji albo sieci pozostaje w widoku.
      setError(requestErrorMessage(requestError))
    } finally {
      // Kontrolka znów przyjmuje kliknięcia.
      setPreferenceSaving(false)
    }
  }

  // Renderujemy właściwy panel analityczny.
  return (
    <div className="dashboard-workspace">
      {/* Pasek informuje o świeżości danych i udostępnia ręczne ponowienie requestu. */}
      <section className="dashboard-toolbar" aria-label="Stan Dashboardu">
        <div>
          <span>Dane wygenerowano {formatDateTime(dashboard.generated_at)}</span>
          <small>
            {dashboard.cache.global_data ? 'Agregacje z Redis' : 'Agregacje z bazy'}
            {authSession && `, lokalizacje ${dashboard.cache.user_data ? 'z Redis' : 'z bazy'}`}
          </small>
        </div>
        <button disabled={loading} onClick={refreshDashboard} type="button">
          {loading ? 'Odświeżanie...' : 'Odśwież'}
        </button>
      </section>

      {/* Segmentowany wybór zapisuje preferencję użytkownika w PostgreSQL. */}
      <section className="dashboard-preferences" aria-label="Domyślny zakres danych">
        <div>
          <strong>Domyślny zakres danych</strong>
          <span>{authSession ? 'Ustawienie jest zapisane na Twoim koncie.' : 'Zaloguj się, aby zapisać wybór.'}</span>
        </div>
        <div className="dashboard-range-control">
          {[
            { value: 24, label: '24 h' },
            { value: 168, label: '7 dni' },
            { value: 720, label: '30 dni' },
          ].map((option) => (
            <button
              className={dashboard.range_hours === option.value ? 'selected' : ''}
              disabled={preferenceSaving}
              key={option.value}
              onClick={() => changeDashboardRange(option.value)}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      </section>

      {/* Błąd odświeżenia nie usuwa wcześniej poprawnie pobranych danych. */}
      {error && <p className="dashboard-inline-error">{error}</p>}

      {/* Pięć kart odpowiada najważniejszym wymaganiom widoku analitycznego. */}
      <section className="dashboard-stats-grid" aria-label="Najważniejsze statystyki">
        {statistics.map((statistic) => (
          <article className="stat-card" key={statistic.label}>
            <span>{statistic.label}</span>
            <strong>{statistic.value}</strong>
          </article>
        ))}
      </section>

      {/* Główna siatka zestawia wykres rozkładu z listą najnowszych zdarzeń. */}
      <section className="dashboard-main-grid">
        <article className="dashboard-panel">
          <div className="dashboard-section-heading">
            <div>
              <span className="eyebrow">Zakres: {dashboard.range_hours} godzin</span>
              <h2>Rozkład magnitud</h2>
            </div>
          </div>
          {/* ResponsiveContainer wymaga rodzica ze stabilną wysokością. */}
          <div className="dashboard-chart">
            <ResponsiveContainer height="100%" width="100%">
              <BarChart data={dashboard.magnitude_distribution}>
                <CartesianGrid stroke="rgba(255,255,255,0.09)" vertical={false} />
                <XAxis dataKey="label" stroke="#b9a6d3" tickLine={false} />
                <YAxis allowDecimals={false} stroke="#b9a6d3" tickLine={false} width={28} />
                <Tooltip
                  contentStyle={{
                    background: '#170b2b',
                    border: '1px solid rgba(255,255,255,0.14)',
                    borderRadius: '6px',
                  }}
                  cursor={{ fill: 'rgba(94,234,212,0.08)' }}
                />
                <Bar dataKey="count" fill="#5eead4" name="Zdarzenia" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="dashboard-panel">
          <div className="dashboard-section-heading">
            <div>
              <span className="eyebrow">Najnowsze dane USGS</span>
              <h2>Ostatnie trzęsienia</h2>
            </div>
          </div>
          {/* Lista pozwala jednym kliknięciem otworzyć zdarzenie na mapie sejsmicznej. */}
          <div className="dashboard-event-list">
            {dashboard.latest_earthquakes.length ? dashboard.latest_earthquakes.map((event) => (
              <button key={event.id} onClick={() => onShowEarthquake(event)} type="button">
                <span>
                  <strong>{event.place || event.title}</strong>
                  <small>{formatDateTime(event.event_time)}</small>
                </span>
                <b>M {formatMagnitude(event.magnitude)}</b>
              </button>
            )) : (
              <p className="dashboard-empty">Brak zapisanych zdarzeń sejsmicznych.</p>
            )}
          </div>
        </article>
      </section>

      {/* Dolna część zestawia prywatną pogodę z obserwowalnością synchronizacji. */}
      <section className="dashboard-lower-grid">
        <article className="dashboard-panel">
          <div className="dashboard-section-heading">
            <div>
              <span className="eyebrow">Twoje dane</span>
              <h2>Pogoda lokalizacji</h2>
            </div>
            {authSession && (
              <button onClick={onShowLocations} type="button">Zarządzaj</button>
            )}
          </div>

          {/* Niezalogowany użytkownik widzi jasną drogę do prywatnej funkcji. */}
          {!authSession ? (
            <div className="dashboard-login-state">
              <span>Zaloguj się, aby zobaczyć pogodę zapisanych miejsc.</span>
              <button onClick={onOpenLogin} type="button">Zaloguj przez Google</button>
            </div>
          ) : dashboard.locations.length ? (
            <div className="dashboard-location-list">
              {dashboard.locations.map((location) => (
                <button key={location.id} onClick={onShowLocations} type="button">
                  <span>
                    <strong>{location.name}</strong>
                    <small>{[location.region, location.country].filter(Boolean).join(', ') || 'Bez opisu regionu'}</small>
                  </span>
                  <span className="dashboard-weather-values">
                    <b>{location.latest_weather ? `${location.latest_weather.temperature} °C` : '-'}</b>
                    <small>
                      {location.latest_weather
                        ? `wilg. ${location.latest_weather.humidity}%, chmury ${location.latest_weather.cloud_cover ?? '-'}%`
                        : 'Brak pomiaru'}
                    </small>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="dashboard-login-state">
              <span>Nie masz jeszcze zapisanych lokalizacji.</span>
              <button onClick={onShowLocations} type="button">Dodaj lokalizację</button>
            </div>
          )}
        </article>

        <article className="dashboard-panel">
          <div className="dashboard-section-heading">
            <div>
              <span className="eyebrow">Automatyzacja danych</span>
              <h2>Ostatnia synchronizacja</h2>
            </div>
          </div>
          {/* Każdy typ zadania ma własny wiersz, status, czas i licznik wyników. */}
          <div className="dashboard-sync-list">
            {Object.entries(dashboard.last_sync).map(([jobType, sync]) => (
              <div className="dashboard-sync-row" key={jobType}>
                <span>
                  <strong>{SYNC_LABELS[jobType]}</strong>
                  <small>{formatDateTime(sync.finished_at || sync.started_at)}</small>
                </span>
                <span className={`dashboard-sync-status status-${sync.status.toLowerCase()}`}>
                  {STATUS_LABELS[sync.status] ?? sync.status}
                </span>
                <b>{sync.items_fetched}</b>
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  )
}

// Eksport domyślny pozwala ładować cięższy moduł Recharts przez React.lazy.
export default DashboardView
