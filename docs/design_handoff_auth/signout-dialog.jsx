// Lab Bridge — Sign-out confirmation dialog
// Modal: backdrop + centered card. Used when the user picks
// "Sign out" from the rail user menu.
/* global React */

function LBSignOutDialog({ lang = "en", user = null, onCancel = () => {}, onConfirm = () => {} }) {
  const t = lang === "ru" ? SIGNOUT_STRINGS.ru : SIGNOUT_STRINGS.en;
  return (
    <div className="lb-modal" role="dialog" aria-modal="true" aria-labelledby="lb-signout-title">
      <div className="lb-modal__backdrop" onClick={onCancel} />
      <div className="lb-modal__card">
        <header className="lb-modal__head">
          <div className="lb-modal__ico" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 8V6.5A1.5 1.5 0 0 0 12.5 5h-6A1.5 1.5 0 0 0 5 6.5v11A1.5 1.5 0 0 0 6.5 19h6a1.5 1.5 0 0 0 1.5-1.5V16" />
              <path d="M19 12H10" />
              <path d="M16 9l3 3-3 3" />
            </svg>
          </div>
          <h2 id="lb-signout-title" className="lb-modal__title">{t.title}</h2>
          <button type="button" className="lb-modal__close" aria-label={t.cancel} onClick={onCancel}>
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <path d="M3 3l8 8M11 3l-8 8" />
            </svg>
          </button>
        </header>

        <div className="lb-modal__body">
          <p className="lb-modal__lede">{t.body}</p>
          {user && (
            <div className="lb-modal__user">
              <span className="lb-rail__avatar" aria-hidden="true" style={{ width: 28, height: 28, fontSize: 11 }}>
                {user.initials}
              </span>
              <div className="lb-modal__user-text">
                <b>{user.name}</b>
              </div>
            </div>
          )}
        </div>

        <footer className="lb-modal__foot">
          <button type="button" className="lb-modal__btn" onClick={onCancel}>{t.cancel}</button>
          <button type="button" className="lb-modal__btn lb-modal__btn--danger" onClick={onConfirm}>
            {t.confirm}
          </button>
        </footer>
      </div>
    </div>
  );
}

const SIGNOUT_STRINGS = {
  en: {
    title:   "Sign out?",
    body:    "You'll be signed out of lab-bridge. Open sessions to JupyterLab, Grafana, and Flasher will end.",
    cancel:  "Cancel",
    confirm: "Sign out",
  },
  ru: {
    title:   "Выйти?",
    body:    "Вы выйдете из lab-bridge. Активные сессии JupyterLab, Grafana и Flasher будут закрыты.",
    cancel:  "Отмена",
    confirm: "Выйти",
  },
};

Object.assign(window, { LBSignOutDialog });