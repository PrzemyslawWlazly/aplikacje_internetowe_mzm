// Hooki Reacta pozwalają zachować kontener przycisku oraz aktualne funkcje callback.
import { useEffect, useRef, useState } from 'react'

// Stały identyfikator zapobiega wielokrotnemu dodaniu skryptu Google do dokumentu.
const GOOGLE_SCRIPT_ID = 'google-identity-services'

// Jedna współdzielona obietnica obsługuje wiele renderów komponentu w tej samej karcie.
let googleScriptPromise = null
// Zapamiętany Client ID chroni bibliotekę Google przed ponowną inicjalizacją przy każdym otwarciu modalu.
let initializedClientId = null
// Wspólny odbiorca przekazuje token do aktualnie zamontowanego komponentu.
let activeCredentialReceiver = null

// Funkcja ładuje oficjalny skrypt Google Identity Services dopiero wtedy, gdy jest potrzebny.
function loadGoogleIdentityScript() {
  // Jeśli globalny obiekt już istnieje, skrypt został wcześniej poprawnie załadowany.
  if (window.google?.accounts?.id) return Promise.resolve()
  // Istniejąca obietnica oznacza, że ładowanie już trwa.
  if (googleScriptPromise) return googleScriptPromise

  // Tworzymy obietnicę zakończoną po zdarzeniu load albo odrzuconą po zdarzeniu error.
  googleScriptPromise = new Promise((resolve, reject) => {
    // Szukamy elementu utworzonego wcześniej, na przykład przez poprzedni render komponentu.
    const existingScript = document.getElementById(GOOGLE_SCRIPT_ID)
    // Jeśli element istnieje, podpinamy obsługę do tego samego pobierania.
    if (existingScript) {
      existingScript.addEventListener('load', resolve, { once: true })
      existingScript.addEventListener('error', reject, { once: true })
      return
    }

    // Tworzymy znacznik script dla oficjalnego klienta logowania Google.
    const script = document.createElement('script')
    // Identyfikator umożliwia odnalezienie elementu przy kolejnych renderach.
    script.id = GOOGLE_SCRIPT_ID
    // Adres pochodzi z dokumentacji Google Identity Services.
    script.src = 'https://accounts.google.com/gsi/client'
    // async pozwala przeglądarce nie blokować renderowania aplikacji.
    script.async = true
    // defer uruchamia kod po przetworzeniu aktualnego dokumentu HTML.
    script.defer = true
    // Sukces kończy obietnicę i pozwala zainicjalizować przycisk.
    script.addEventListener('load', resolve, { once: true })
    // Błąd sieci odrzuca obietnicę i zostanie pokazany użytkownikowi.
    script.addEventListener('error', reject, { once: true })
    // Umieszczamy skrypt w head, zgodnie ze standardowym sposobem ładowania bibliotek.
    document.head.appendChild(script)
  })

  // Zwracamy współdzieloną obietnicę wszystkim wywołaniom.
  return googleScriptPromise
}

// Komponent renderuje oficjalny przycisk Google w przygotowanym kontenerze.
function GoogleSignIn({ clientId, disabled, onCredential, onError }) {
  // Ref wskazuje element DOM, do którego biblioteka Google wstawi przycisk.
  const buttonContainerRef = useRef(null)
  // Ref przechowuje najnowszy callback bez ponownej inicjalizacji Google po każdym renderze.
  const credentialCallbackRef = useRef(onCredential)
  // Lokalny błąd opisuje problem z konfiguracją albo pobraniem skryptu.
  const [scriptError, setScriptError] = useState('')
  // Brak Client ID jest stałym błędem konfiguracji, więc wyliczamy go bez dodatkowego renderu efektu.
  const configurationError = clientId ? '' : 'Brak VITE_GOOGLE_CLIENT_ID w konfiguracji frontendu.'
  // Komunikat konfiguracji ma pierwszeństwo przed ewentualnym błędem pobierania skryptu.
  const displayedError = configurationError || scriptError

  // Aktualizujemy callback zawsze, gdy rodzic przekaże jego nową wersję.
  useEffect(() => {
    credentialCallbackRef.current = onCredential
  }, [onCredential])

  // Efekt podłącza aktualny komponent do jednego globalnego callbacku biblioteki Google.
  useEffect(() => {
    // Funkcja pośrednia zawsze odczytuje najnowszy callback rodzica z refa.
    const receiver = (credential) => credentialCallbackRef.current(credential)
    // Globalny odbiorca działa również wtedy, gdy Google zostało zainicjalizowane przy poprzednim otwarciu modalu.
    activeCredentialReceiver = receiver

    // Cleanup usuwa wyłącznie odbiorcę należącego do tego renderu komponentu.
    return () => {
      if (activeCredentialReceiver === receiver) activeCredentialReceiver = null
    }
  }, [])

  // Efekt inicjalizuje bibliotekę po pojawieniu się Client ID i kontenera.
  useEffect(() => {
    // Flaga chroni przed modyfikacją komponentu po jego zamknięciu.
    let active = true

    // Brak Client ID oznacza, że administrator musi dokończyć konfigurację środowiska.
    if (!clientId) {
      return undefined
    }

    // Po załadowaniu skryptu konfigurujemy sposób odbioru tokenu ID.
    loadGoogleIdentityScript()
      .then(() => {
        // Nie wykonujemy pracy, jeśli modal został w międzyczasie zamknięty.
        if (!active || !buttonContainerRef.current) return
        // Czyścimy kontener, aby przy ponownym otwarciu nie powielać przycisków.
        buttonContainerRef.current.replaceChildren()
        // Inicjalizujemy klienta tylko raz dla danego Client ID, również po ponownym otwarciu modalu.
        if (initializedClientId !== clientId) {
          // Inicjalizacja ustawia wspólny odbiornik tokenu oraz wyłącza automatyczny wybór konta.
          window.google.accounts.id.initialize({
            client_id: clientId,
            callback: (response) => activeCredentialReceiver?.(response.credential),
            auto_select: false,
            cancel_on_tap_outside: true,
          })
          // Zapamiętujemy konfigurację, aby następny modal tylko wyrenderował przycisk.
          initializedClientId = clientId
        }
        // Oficjalny renderer zapewnia zgodność przycisku z zasadami marki Google.
        window.google.accounts.id.renderButton(buttonContainerRef.current, {
          type: 'standard',
          theme: 'filled_black',
          size: 'large',
          text: 'signin_with',
          shape: 'rectangular',
          logo_alignment: 'left',
          locale: 'pl',
          width: 280,
        })
      })
      .catch(() => {
        // Błąd może wynikać z braku internetu, blokady skryptów lub rozszerzenia prywatności.
        if (active) setScriptError('Nie udało się załadować logowania Google.')
      })

    // Cleanup zatrzymuje callbacki po usunięciu komponentu.
    return () => {
      active = false
    }
  }, [clientId])

  // Przekazujemy błąd również do rodzica, aby mógł pokazać wspólny komunikat formularza.
  useEffect(() => {
    if (displayedError) onError(displayedError)
  }, [displayedError, onError])

  // Renderujemy stabilne miejsce na przycisk oraz warstwę blokującą kliknięcie podczas requestu.
  return (
    <div className={disabled ? 'google-sign-in disabled' : 'google-sign-in'}>
      {/* Biblioteka Google sama umieszcza właściwy przycisk w tym elemencie. */}
      <div ref={buttonContainerRef} />
      {/* Przezroczysta warstwa zapobiega wysłaniu dwóch requestów podczas logowania. */}
      {disabled && <span aria-hidden="true" className="google-sign-in-blocker" />}
    </div>
  )
}

// Eksport domyślny upraszcza import komponentu w głównym pliku aplikacji.
export default GoogleSignIn
