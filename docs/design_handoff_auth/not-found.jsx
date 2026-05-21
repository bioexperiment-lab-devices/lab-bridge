// Lab Bridge — Page not found (404)
// Generic 404 — for any path the router can't resolve. Rail stays.
/* global React */

function LBNotFound({ lang = "en", attemptedPath = "/lab/benchz-42" }) {
  const t = lang === "ru" ? NOT_FOUND_STRINGS.ru : NOT_FOUND_STRINGS.en;
  return (
    <div className="lb-page lb-forbidden-page">
      <main className="lb-forbidden">
        <span className="lb-forbidden__code">Error 404 · Not found</span>

        <div className="lb-forbidden__card">
          <div className="lb-forbidden__head">
            <div className="lb-forbidden__lock lb-forbidden__lock--404" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="10.5" cy="10.5" r="5.5" />
                <path d="M14.6 14.6L19 19" />
                <path d="M8.5 10.5h4" />
              </svg>
            </div>
            <h1 className="lb-forbidden__title">{t.title}</h1>
          </div>
          <p className="lb-forbidden__body">{t.body}</p>

          <dl className="lb-forbidden__meta">
            <div>
              <dt>{t.metaPath}</dt>
              <dd><code>{attemptedPath}</code></dd>
            </div>
          </dl>

          <div className="lb-forbidden__actions">
            <button type="button" className="lb-forbidden__primary" onClick={() => window.history.back()}>
              <span aria-hidden="true">←</span>
              <span>{t.back}</span>
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

const NOT_FOUND_STRINGS = {
  en: {
    title:    "Page not found",
    body:     "We couldn't find that page. The link may be broken or the resource may have been renamed.",
    metaPath: "Attempted path",
    back:     "Back",
  },
  ru: {
    title:    "Страница не найдена",
    body:     "Не удалось найти эту страницу. Возможно, ссылка устарела или ресурс был переименован.",
    metaPath: "Запрошенный путь",
    back:     "Назад",
  },
};

Object.assign(window, { LBNotFound });