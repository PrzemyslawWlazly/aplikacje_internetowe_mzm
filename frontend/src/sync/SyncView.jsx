// Hooki Reacta obsługują logi, odświeżanie i stan uruchamianych zadań.
import { useCallback, useEffect, useState } from 'react'

// Funkcje API komunikują się z chronionymi endpointami administratora.
import { fetchSyncStatus, startSynchronization } from './api'

// Typy backendu otrzymują krótkie polskie nazwy.
const JOB_LABELS = {
  EARTHQUAKE_SYNC: 'Trzęsienia ziemi', // Import danych USGS.
  WEATHER_SYNC: 'Pogoda lokalizacji', // Odświeżenie zapisanych punktów.
  VOLCANO_SYNC: 'Katalog wulkanów', // Import katalogu i erupcji Smithsonian GVP.
}

// Polecenia są opisane niezależnie od technicznych wartości modelu.
const SYNC_ACTIONS = [
  { type: 'earthquakes', label: 'Synchronizuj trzęsienia', description: 'Pobierz najnowszą paczkę USGS.' },
  { type: 'weather', label: 'Synchronizuj pogodę', description: 'Odśwież zapisane lokalizacje.' },
  { type: 'volcanoes', label: 'Synchronizuj wulkany', description: 'Pobierz katalog i VEI ze Smithsonian GVP.' },
]

// Funkcja formatuje czas logu w lokalnej strefie przeglądarki.
function formatDateTime(value) {
  // Trwające zadanie może nie mieć czasu zakończenia.
  if (!value) return '-'
  // Pełna data pomaga administratorowi odróżnić kolejne uruchomienia.
  return new Date(value).toLocaleString('pl-PL')
}

// Funkcja wyciąga komunikat backendu albo błąd sieci.
function requestErrorMessage(error) {
  // Detail ma pierwszeństwo przed domyślnym tekstem Axios.
  return error.response?.data?.detail ?? error.message ?? 'Operacja synchronizacji nie powiodła się.'
}

// Komponent przedstawia panel dostępny wyłącznie użytkownikowi staff.
function SyncView({ authSession, requestWithAuth }) {
  // Lista zawiera maksymalnie pięćdziesiąt ostatnich rekordów SyncJob.
  const [jobs, setJobs] = useState([])
  // Loading dotyczy pobierania historii.
  const [loading, setLoading] = useState(Boolean(authSession?.user?.is_staff))
  // RunningType blokuje tylko polecenie aktualnie wysyłane do Celery.
  const [runningType, setRunningType] = useState('')
  // Komunikat sukcesu potwierdza przekazanie zadania do kolejki.
  const [notice, setNotice] = useState('')
  // Błąd uprawnień albo brokera pozostaje widoczny nad logami.
  const [error, setError] = useState('')

  // Callback pobiera status przez wrapper automatycznie odnawiający JWT.
  const loadStatus = useCallback(async () => {
    // Czyścimy błąd poprzedniego odczytu.
    setError('')
    // Informujemy o pobieraniu listy.
    setLoading(true)

    try {
      // Endpoint sam sprawdza flagę is_staff po stronie backendu.
      const data = await requestWithAuth(fetchSyncStatus)
      // Zapisujemy zwróconą listę logów.
      setJobs(data.results ?? [])
    } catch (requestError) {
      // Błąd 403 albo problem sieci jest pokazany administratorowi.
      setError(requestErrorMessage(requestError))
    } finally {
      // Kończymy stan ładowania.
      setLoading(false)
    }
  }, [requestWithAuth])

  // Po wejściu do zakładki od razu pobieramy historię.
  useEffect(() => {
    // Brak konta staff nie powinien wykonywać requestu administracyjnego.
    if (!authSession?.user?.is_staff) {
      return
    }
    // Zerowy timer przenosi aktualizacje stanu poza synchroniczną fazę efektu Reacta.
    const timerId = window.setTimeout(loadStatus, 0)
    // Cleanup zapobiega uruchomieniu requestu po natychmiastowym opuszczeniu panelu.
    return () => window.clearTimeout(timerId)
  }, [authSession?.user?.is_staff, loadStatus])

  // Funkcja przekazuje wybrane zadanie do kolejki.
  async function runSynchronization(jobType) {
    // Czyścimy poprzednie komunikaty przed nową operacją.
    setError('')
    setNotice('')
    // Blokujemy kliknięty przycisk.
    setRunningType(jobType)

    try {
      // Redis przyjmuje zadanie, a worker wykona właściwą usługę poza requestem HTTP.
      const result = await requestWithAuth(
        (accessToken) => startSynchronization(accessToken, jobType),
      )
      // Pokazujemy id zadania jako dowód asynchronicznego uruchomienia.
      setNotice(`Zadanie ${result.task_id} zostało dodane do kolejki.`)
      // Krótka zwłoka pozwala workerowi utworzyć rekord RUNNING przed odświeżeniem.
      window.setTimeout(loadStatus, 900)
    } catch (requestError) {
      // Błąd brokera lub uprawnień jest przedstawiony bez ukrywania poprzednich logów.
      setError(requestErrorMessage(requestError))
    } finally {
      // Odblokowujemy polecenie po odpowiedzi endpointu 202 albo błędzie.
      setRunningType('')
    }
  }

  // Dodatkowa ochrona UI nie zastępuje IsAdminUser, ale jasno komunikuje rolę konta.
  if (!authSession?.user?.is_staff) {
    return (
      <section className="sync-access-state">
        <strong>Panel dostępny tylko dla administratora.</strong>
        <span>Uprawnienie jest sprawdzane również przez backend.</span>
      </section>
    )
  }

  // Renderujemy polecenia i logi z relacyjnej bazy.
  return (
    <div className="sync-workspace">
      {/* Każdy rodzaj synchronizacji ma osobną, jasno opisaną komendę. */}
      <section className="sync-actions" aria-label="Ręczne synchronizacje">
        {SYNC_ACTIONS.map((action) => (
          <article key={action.type}>
            <div>
              <strong>{action.label}</strong>
              <span>{action.description}</span>
            </div>
            <button
              disabled={Boolean(runningType)}
              onClick={() => runSynchronization(action.type)}
              type="button"
            >
              {runningType === action.type ? 'Dodawanie...' : 'Uruchom'}
            </button>
          </article>
        ))}
      </section>

      {/* Komunikaty nie zmieniają wymiarów tabeli logów. */}
      {notice && <p className="sync-notice">{notice}</p>}
      {error && <p className="dashboard-inline-error">{error}</p>}

      {/* Nagłówek historii zawiera ręczne odświeżenie bez automatycznego spamowania endpointu. */}
      <section className="sync-history-heading">
        <div>
          <span className="eyebrow">PostgreSQL / SyncJob</span>
          <h2>Historia synchronizacji</h2>
        </div>
        <button disabled={loading} onClick={loadStatus} type="button">
          {loading ? 'Pobieranie...' : 'Odśwież logi'}
        </button>
      </section>

      {/* Tabela pokazuje sukcesy, błędy i zadania aktualnie wykonywane. */}
      <div className="seismic-table-wrap">
        <table className="seismic-table sync-table">
          <thead>
            <tr>
              <th scope="col">Typ</th>
              <th scope="col">Status</th>
              <th scope="col">Start</th>
              <th scope="col">Koniec</th>
              <th scope="col">Elementy</th>
              <th scope="col">Błąd</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>{JOB_LABELS[job.job_type] ?? job.job_type}</td>
                <td>
                  <span className={`dashboard-sync-status status-${job.status.toLowerCase()}`}>
                    {job.status}
                  </span>
                </td>
                <td>{formatDateTime(job.started_at)}</td>
                <td>{formatDateTime(job.finished_at)}</td>
                <td>{job.items_fetched}</td>
                <td className="sync-error-cell" title={job.error_message}>{job.error_message || '-'}</td>
              </tr>
            ))}
            {!loading && !jobs.length && (
              <tr>
                <td className="seismic-empty-cell" colSpan={6}>Brak zapisanych synchronizacji.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// Eksport domyślny wspiera lazy loading panelu administratora.
export default SyncView
