// Lab Bridge — Access denied (403) page
// Shown when an authenticated user tries to open a resource their
// role doesn't grant access to. The rail stays — this is NOT a logout.
/* global React, LB_ICONS, LBAuthContext */

function LBForbidden({ lang = "en", attemptedPath = "/admin/users", requiredRole = "admin" }) {
  const t = lang === "ru" ? FORBIDDEN_STRINGS.ru : FORBIDDEN_STRINGS.en;
  const user = React.useContext(LBAuthContext);
  return (
    <div className="lb-page lb-forbidden-page">
      <main className="lb-forbidden">
        <span className="lb-forbidden__code">Error 403 · Forbidden</span>

        <div className="lb-forbidden__card">
          <div className="lb-forbidden__head">
            <div className="lb-forbidden__lock" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <rect x="5" y="11" width="14" height="9" rx="1.5" />
                <path d="M8 11V8a4 4 0 018 0v3" />
                <circle cx="12" cy="15.5" r="1.25" fill="currentColor" stroke="none" />
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

const FORBIDDEN_STRINGS = {
  en: {
    title:        "You don't have access to this page",
    body:         "This area is restricted to a different role. If you need access for your work, ask the server administrator to update your permissions.",
    metaPath:     "Attempted path",
    back:         "Back",
  },
  ru: {
    title:        "У вас нет доступа к этой странице",
    body:         "Раздел доступен только для другой роли. Если доступ нужен для работы, обратитесь к администратору сервера для изменения прав.",
    metaPath:     "Запрошенный путь",
    back:         "Назад",
  },
};

Object.assign(window, { LBForbidden });