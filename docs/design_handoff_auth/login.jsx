// Lab Bridge — Sign-in page (/sign-in)
// Minimal credentials form: username + password.
// Sign-up is intentionally absent — credentials are issued by admin.
/* global React, LB_ICONS, LBBrandMark */

function LBLogin({ lang = "en", error = null, loading = false }) {
  const t = lang === "ru" ? LOGIN_STRINGS.ru : LOGIN_STRINGS.en;
  const [u, setU] = React.useState("");
  const [p, setP] = React.useState("");
  const [show, setShow] = React.useState(false);
  const [remember, setRemember] = React.useState(false);

  return (
    <div className="lb-page lb-login-page">
      <main className="lb-login">
        <form className="lb-login__card" onSubmit={(e) => e.preventDefault()}>
          <h1 className="lb-login__title">{t.title}</h1>

          {error && (
            <div className="lb-login__error" role="alert">
              <span className="lb-login__error-mark" aria-hidden="true">!</span>
              <span>{error}</span>
            </div>
          )}

          <div className="lb-field">
            <label className="lb-field__label" htmlFor="lb-username">{t.username}</label>
            <input id="lb-username"
                   className="lb-field__input"
                   type="text"
                   autoComplete="username"
                   spellCheck="false"
                   autoCapitalize="off"
                   value={u}
                   onChange={(e) => setU(e.target.value)}
                   placeholder={t.usernamePh} />
          </div>

          <div className="lb-field">
            <label className="lb-field__label" htmlFor="lb-password">{t.password}</label>
            <div className="lb-field__wrap">
              <input id="lb-password"
                     className="lb-field__input"
                     type={show ? "text" : "password"}
                     autoComplete="current-password"
                     value={p}
                     onChange={(e) => setP(e.target.value)}
                     placeholder={t.passwordPh} />
              <button type="button"
                      className="lb-field__reveal"
                      aria-label={show ? t.hide : t.show}
                      aria-pressed={show}
                      onClick={() => setShow(s => !s)}>
                {show ? LoginIcons.eyeOff : LoginIcons.eye}
              </button>
            </div>
          </div>

          <label className="lb-check">
            <input type="checkbox"
                   className="lb-check__input"
                   checked={remember}
                   onChange={(e) => setRemember(e.target.checked)} />
            <span className="lb-check__box" aria-hidden="true">
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 7l3 3 5-6" />
              </svg>
            </span>
            <span className="lb-check__text">
              <span className="lb-check__label">{t.remember}</span>
              <span className="lb-check__hint">{t.rememberHint}</span>
            </span>
          </label>

          <button type="submit"
                  className="lb-login__submit"
                  disabled={loading || !u || !p}>
            {loading ? <span className="lb-login__spinner" aria-hidden="true" /> : LoginIcons.arrow}
            <span>{loading ? t.signingIn : t.submit}</span>
          </button>

          <footer className="lb-login__foot">
            <span className="lb-login__foot-lock" aria-hidden="true">{LB_ICONS.signin}</span>
            <span>{t.adminNote}</span>
          </footer>
        </form>
      </main>
    </div>
  );
}

// Minimal inline icons (eye / eye-off / arrow / spinner via CSS)
const LoginIcons = {
  eye: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8s-2.4 4.5-6.5 4.5S1.5 8 1.5 8z" />
      <circle cx="8" cy="8" r="2" />
    </svg>
  ),
  eyeOff: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2.5 4.5L13.5 13.5" />
      <path d="M5.5 5.2C3.4 6.2 1.5 8 1.5 8s2.4 4.5 6.5 4.5c1.2 0 2.2-.3 3.1-.8" />
      <path d="M10.7 10.7A2 2 0 016 8M9.3 5.2A2 2 0 0110 8" />
      <path d="M14.5 8s-1.4-2.6-3.6-3.8" />
    </svg>
  ),
  arrow: (
    <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 7h8M7.5 3.5L11 7l-3.5 3.5" />
    </svg>
  ),
};

const LOGIN_STRINGS = {
  en: {
    title:      "Sign in to lab-bridge",
    lede:       "Use the credentials issued by your server administrator.",
    username:   "Username",
    usernamePh: "e.g. a.volkova",
    password:   "Password",
    passwordPh: "••••••••",
    show:       "Show password",
    hide:       "Hide password",
    remember:    "Keep me signed in",
    rememberHint:"Stay signed in for 90 days on this device.",
    submit:     "Sign in",
    signingIn:  "Signing in…",
    adminNote:  "No account? Ask your server administrator — sign-up is not public.",
    legal:      "lab-bridge — an internal lab platform. Access is logged.",
  },
  ru: {
    title:      "Вход в lab-bridge",
    lede:       "Используйте учётные данные, выданные администратором сервера.",
    username:   "Имя пользователя",
    usernamePh: "напр. a.volkova",
    password:   "Пароль",
    passwordPh: "••••••••",
    show:       "Показать пароль",
    hide:       "Скрыть пароль",
    remember:    "Оставаться в системе",
    rememberHint:"Не выходить 90 дней на этом устройстве.",
    submit:     "Войти",
    signingIn:  "Вход…",
    adminNote:  "Нет учётной записи? Обратитесь к администратору сервера — публичной регистрации нет.",
    legal:      "lab-bridge — внутренняя платформа лаборатории. Все входы логируются.",
  },
};

Object.assign(window, { LBLogin });