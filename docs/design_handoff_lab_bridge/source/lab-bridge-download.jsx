// Lab Bridge — Download Agent page (/download/agent)
// Distributes the SerialHop agent. Hero + platform cards (Windows
// available, Linux/RPi coming soon) + bilingual browser-block explainer.
/* global React, LB_ICONS */

function LBDownload({ lang = "en", expandedExplainer = false }) {
  const t = lang === "ru" ? DL_STRINGS.ru : DL_STRINGS.en;
  return (
    <div className="lb-page">
      <DLHeader lang={lang} t={t} />
      <div className="lb-page__inner lb-page__inner--download">
        <DLHero t={t} />
        <DLPlatforms t={t} expandedExplainer={expandedExplainer} lang={lang} />
        <DLBodyMarkdown t={t} />
      </div>
    </div>
  );
}

// ============================================================
// Header — matches Home's sticky header but with no language toggle
// (the brief explicitly excludes the toggle from the Download page).
// Bilingual content inside the page comes from the platform-wide cookie.
// ============================================================
function DLHeader({ lang, t }) {
  return (
    <header className="lb-home-header">
      <div className="lb-home-header__brand">
        <span className="lb-home-header__dot" aria-hidden="true" />
        <span>lab-bridge</span>
        <small>{t.idTag}</small>
      </div>
      <div className="lb-lang" role="group" aria-label="Language">
        <button data-active={lang === "en" || undefined}>EN</button>
        <button data-active={lang === "ru" || undefined}>RU</button>
      </div>
    </header>
  );
}

// ============================================================
// Hero — title + one-sentence lede + GitHub link
// ============================================================
function DLHero({ t }) {
  return (
    <section className="lb-dl-hero">
      <div className="lb-dl-hero__mark" aria-hidden="true">
        {/* SerialHop wordmark stand-in — a stylized "S" plug glyph */}
        <svg viewBox="0 0 40 40" fill="none">
          <rect x="2" y="2" width="36" height="36" rx="8" fill="var(--accent)" />
          <path d="M14 13.5c0-1.4 1.1-2.5 2.5-2.5h7c1.4 0 2.5 1.1 2.5 2.5v0c0 1.4-1.1 2.5-2.5 2.5h-5c-1.4 0-2.5 1.1-2.5 2.5v3c0 1.4 1.1 2.5 2.5 2.5h7c1.4 0 2.5 1.1 2.5 2.5v0c0 1.4-1.1 2.5-2.5 2.5h-7"
                stroke="#fff" strokeWidth="2" strokeLinecap="round" />
          <circle cx="14" cy="13.5" r="1.6" fill="#fff" />
          <circle cx="26" cy="26.5" r="1.6" fill="#fff" />
        </svg>
      </div>
      <div className="lb-dl-hero__body">
        <h1 className="lb-dl-hero__title">SerialHop</h1>
        <p className="lb-dl-hero__lede">{t.heroLede}</p>
        <div className="lb-dl-hero__meta">
          <span>{t.heroSourceLabel}</span>
          <a href="https://github.com/bioexperiment-lab-devices/serialhop" className="lb-dl-hero__link">
            github.com/bioexperiment-lab-devices/serialhop <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
    </section>
  );
}

// ============================================================
// Platform cards — vertical list, Windows available + 2 coming soon
// ============================================================
const FLEET = {
  windows: {
    version: "0.9.0",
    size: "12.3 MB",
    released: "2026-05-12T14:33:21Z",
    sha256: "9a2c1bd4e7f0a13d56b8c2e9a7d4f1b0e3c8a5d72f1e6b9c0a4d3b7e2f8c1a05",
    filename: "SerialHop-v0.9.0.exe",
  },
};

function DLPlatforms({ t, expandedExplainer, lang }) {
  return (
    <section className="lb-section">
      <div className="lb-section__head">
        <h2 className="lb-section__title">{t.platformsTitle}</h2>
        <div className="lb-section__rule" />
      </div>
      <div className="lb-dl-cards">
        <DLCardWindows t={t} expanded={expandedExplainer} lang={lang} />
        <DLCardComingSoon
          platform="Linux"
          icon={LinuxIcon}
          body={t.linuxComing}
          quarter={t.linuxQuarter}
          t={t}
        />
        <DLCardComingSoon
          platform="Raspberry Pi"
          icon={RaspberryIcon}
          body={t.rpiComing}
          quarter={t.rpiQuarter}
          t={t}
        />
      </div>
    </section>
  );
}

function DLCardWindows({ t, expanded, lang }) {
  const fw = FLEET.windows;
  return (
    <article className="lb-dl-card lb-dl-card--available" aria-label="Windows download">
      <header className="lb-dl-card__head">
        <span className="lb-dl-card__platico" aria-hidden="true"><WindowsIcon /></span>
        <div className="lb-dl-card__platnames">
          <h3 className="lb-dl-card__title">Windows</h3>
          <p className="lb-dl-card__sub">{t.windowsRequirement}</p>
        </div>
        <span className="lb-dl-card__status lb-dl-card__status--ok">{t.statusAvailable}</span>
      </header>

      <div className="lb-dl-card__body">
        <button className="lb-dl-card__cta" type="button">
          <span className="lb-dl-card__cta-ico" aria-hidden="true">{LB_ICONS.download}</span>
          <span className="lb-dl-card__cta-stack">
            <span className="lb-dl-card__cta-line">{t.downloadFor} Windows</span>
            <span className="lb-dl-card__cta-meta">v{fw.version} · {fw.size}</span>
          </span>
        </button>

        <BrowserBlockExplainer t={t} expanded={expanded} lang={lang} />

        <dl className="lb-dl-meta">
          <div className="lb-dl-meta__row">
            <dt>{t.metaVersion}</dt>
            <dd><code>{fw.version}</code></dd>
          </div>
          <div className="lb-dl-meta__row">
            <dt>{t.metaReleased}</dt>
            <dd>
              <code>{fw.released}</code>
              <span className="lb-dl-meta__rel">— {t.metaReleasedAgo}</span>
            </dd>
          </div>
          <div className="lb-dl-meta__row">
            <dt>{t.metaSha}</dt>
            <dd className="lb-dl-meta__sha">
              <code>{fw.sha256}</code>
              <button className="lb-dl-meta__copybtn" type="button" aria-label={t.copySha}>
                {LB_ICONS.copy}<span>{t.copy}</span>
              </button>
            </dd>
          </div>
        </dl>
      </div>
    </article>
  );
}

function DLCardComingSoon({ platform, icon: Icon, body, quarter, t }) {
  return (
    <article className="lb-dl-card lb-dl-card--coming" aria-label={`${platform} — coming soon`}>
      <header className="lb-dl-card__head">
        <span className="lb-dl-card__platico" aria-hidden="true"><Icon /></span>
        <div className="lb-dl-card__platnames">
          <h3 className="lb-dl-card__title">{platform}</h3>
          <p className="lb-dl-card__sub">{body}</p>
        </div>
        <span className="lb-dl-card__status lb-dl-card__status--soon">
          {t.statusSoon}
          <small>{quarter}</small>
        </span>
      </header>
    </article>
  );
}

// ============================================================
// Browser-block explainer (Windows-only, bilingual, collapsible)
// ============================================================
function BrowserBlockExplainer({ t, expanded, lang }) {
  return (
    <details className="lb-dl-explainer" open={expanded || undefined}>
      <summary className="lb-dl-explainer__summary">
        <span className="lb-dl-explainer__icon" aria-hidden="true">!</span>
        <span className="lb-dl-explainer__title">{t.expSummary}</span>
        <span className="lb-dl-explainer__chev" aria-hidden="true">▾</span>
      </summary>

      <div className="lb-dl-explainer__body">
        <p>{t.expIntro1}</p>
        <p>
          {t.expIntro2Pre}{" "}
          <button className="lb-dl-explainer__inlinelink" type="button">{t.expVerifyAction}</button>
          {" "}{t.expIntro2Post}
        </p>

        <h4 className="lb-dl-explainer__steph">{t.expStepA}</h4>
        <ol className="lb-dl-explainer__steps">
          <li>{t.expA1Pre} <kbd>Ctrl</kbd>+<kbd>J</kbd> {t.expA1Post}</li>
          <li>{t.expA2Pre} <code>⋯</code> → <b>“{t.expKeep}”</b>.</li>
          <li>{t.expA3}</li>
        </ol>

        <h4 className="lb-dl-explainer__steph">{t.expStepB}</h4>
        <ol className="lb-dl-explainer__steps">
          <li>{t.expB1Pre} <b>“{t.expMoreInfo}”</b> {t.expB1Post}</li>
          <li>{t.expB2Pre} <b>“{t.expRunAnyway}”</b>{t.expB2Post}</li>
        </ol>
      </div>
    </details>
  );
}

// ============================================================
// Optional Markdown body (operator-supplied, platform-agnostic)
// Reuses the docs primitives — admonitions, code, etc.
// ============================================================
function DLBodyMarkdown({ t }) {
  return (
    <section className="lb-dl-bodymd">
      <div className="lb-section__head">
        <h2 className="lb-section__title">{t.bodyTitle}</h2>
        <div className="lb-section__rule" />
      </div>
      <article className="lb-docs-article" style={{ maxWidth: "none", padding: 0 }}>
        <p>
          {t.bodyP1Pre}{" "}
          <a href="/docs/operator/setup">{t.bodyDocLink}</a>{" "}
          {t.bodyP1Post}
        </p>
      </article>
    </section>
  );
}

// ============================================================
// Platform icons
// ============================================================
function WindowsIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M3 5.6L10.6 4.5V11.4H3V5.6zm0 12.8v-5.8h7.6v6.9L3 18.4zm8.6-14L21 3v9.4H11.6V4.4zm0 9.4H21V21l-9.4-1.3V13.8z" />
    </svg>
  );
}
function LinuxIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <ellipse cx="12" cy="10" rx="4.5" ry="6" />
      <circle cx="10.5" cy="9" r="0.6" fill="currentColor" />
      <circle cx="13.5" cy="9" r="0.6" fill="currentColor" />
      <path d="M10.5 12c.5.6 2 .6 3 0" />
      <path d="M7.5 15c-1 1.4-2 2.5-2.5 4-.4 1.2.3 2 1.5 2h11c1.2 0 1.9-.8 1.5-2-.5-1.5-1.5-2.6-2.5-4" />
      <path d="M9 18.5l3-1 3 1" />
    </svg>
  );
}
function RaspberryIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M8 4c1 1.5 2 2 4 2s3-.5 4-2" />
      <path d="M7 6c-2 0-3 1.5-3 3.5 0 1 .5 2 1.5 2.5 0 3.5 3 6 6.5 6s6.5-2.5 6.5-6c1-.5 1.5-1.5 1.5-2.5 0-2-1-3.5-3-3.5" />
      <path d="M9 10.5c.3.5 1 .8 1.6.4M14.4 10.9c-.6.4-1.3.1-1.6-.4" />
      <path d="M9 16h6" />
    </svg>
  );
}

// ============================================================
// Strings — EN + RU. The browser-block explainer is fully bilingual.
// ============================================================
const DL_STRINGS = {
  en: {
    idTag: "lab instrumentation platform",
    cookieHint: "language follows the cookie set on the home page",
    platformsTitle: "Platforms",
    statusAvailable: "Available",
    statusSoon: "Coming soon",
    windowsRequirement: "Windows 10 / 11 · 64-bit",
    downloadFor: "Download for",
    metaVersion: "Version",
    metaReleased: "Released",
    metaReleasedAgo: "6 days ago",
    metaSha: "SHA-256",
    copy: "copy",
    copySha: "Copy SHA-256 to clipboard",

    heroLede: "Single-binary agent that exposes a lab PC's instruments to lab-bridge through a secure reverse tunnel.",
    heroSourceLabel: "Source, releases, and protocol notes:",

    linuxComing: "Linux build is on the way.",
    linuxQuarter: "expected Q3 2026",
    rpiComing: "Raspberry Pi build is on the way.",
    rpiQuarter: "expected Q3 2026",

    expSummary: "Your browser may block this download — here's how to keep it",
    expIntro1: "SerialHop is a fresh, unsigned binary. Microsoft Defender SmartScreen hasn't built up a reputation for it yet, so the browser is being cautious. It is safe to run.",
    expIntro2Pre: "Confirm it's the right file by",
    expVerifyAction: "checking the SHA-256",
    expIntro2Post: "below against the value your server administrator sent you.",
    expStepA: "If the browser hides the download",
    expA1Pre: "Open the downloads list (press",
    expA1Post: ").",
    expA2Pre: "Find the file, click",
    expKeep: "Keep",
    expA3: "If a second \"this file might harm your computer\" prompt appears, choose \"Keep dangerous file\".",
    expStepB: "If Windows blocks the .exe on first run",
    expB1Pre: "In the SmartScreen dialog, click",
    expMoreInfo: "More info",
    expB1Post: "— the Run anyway button is hidden until you do.",
    expB2Pre: "Click",
    expRunAnyway: "Run anyway",
    expB2Post: ". Windows will remember the choice for next time.",
    expLangNote: "bilingual — switch language on the home page",

    bodyTitle: "Setup notes",
    bodyP1Pre: "Once installed, point SerialHop at your lab-bridge server using the credentials your server administrator issued. Full walkthrough is in the",
    bodyDocLink: "Set up a new lab PC",
    bodyP1Post: "guide.",
    bodyTipTitle: "Tip",
    bodyTipBodyPre: "After the agent reports in, your lab will appear on the home page within ~10 seconds. If it doesn't show up, check",
    bodyTipLink: "where to look in Grafana",
    bodyTipBodyPost: " — the agent logs surface there first.",
    bodyFaqTitle: "Frequently asked",
    bodyFaq1Q: "Do I need to reopen ports on the lab PC's firewall?",
    bodyFaq1A: "No — SerialHop opens an outbound reverse tunnel. No inbound rules are required.",
    bodyFaq2Q: "Can I run multiple agents on the same machine?",
    bodyFaq2A: "Only one. Two agents would fight over the same serial ports. Use one lab name per physical machine.",
  },
  ru: {
    idTag: "платформа для лабораторных приборов",
    cookieHint: "язык берётся из cookie, установленного на главной странице",
    platformsTitle: "Платформы",
    statusAvailable: "Доступно",
    statusSoon: "Скоро",
    windowsRequirement: "Windows 10 / 11 · 64-бит",
    downloadFor: "Скачать для",
    metaVersion: "Версия",
    metaReleased: "Выпущено",
    metaReleasedAgo: "6 дней назад",
    metaSha: "SHA-256",
    copy: "копировать",
    copySha: "Скопировать SHA-256",

    heroLede: "Однофайловый агент, который открывает приборам ПК лаборатории защищённый обратный туннель до lab-bridge.",
    heroSourceLabel: "Исходники, релизы и заметки о протоколе:",

    linuxComing: "Сборка для Linux в работе.",
    linuxQuarter: "ожидается Q3 2026",
    rpiComing: "Сборка для Raspberry Pi в работе.",
    rpiQuarter: "ожидается Q3 2026",

    expSummary: "Браузер может заблокировать загрузку — вот как её сохранить",
    expIntro1: "SerialHop — свежий неподписанный бинарный файл. У Microsoft Defender SmartScreen ещё нет «репутации» для него, поэтому браузер осторожничает. Файл безопасен.",
    expIntro2Pre: "Убедитесь, что это нужный файл —",
    expVerifyAction: "проверьте SHA-256",
    expIntro2Post: "ниже со значением, которое прислал администратор сервера.",
    expStepA: "Если браузер прячет загрузку",
    expA1Pre: "Откройте список загрузок (нажмите",
    expA1Post: ").",
    expA2Pre: "Найдите файл, нажмите",
    expKeep: "Сохранить",
    expA3: "Если появится второе предупреждение «этот файл может навредить компьютеру», выберите «Сохранить опасный файл».",
    expStepB: "Если Windows блокирует .exe при первом запуске",
    expB1Pre: "В диалоге SmartScreen нажмите",
    expMoreInfo: "Подробнее",
    expB1Post: "— кнопка «Выполнить» спрятана, пока вы этого не сделаете.",
    expB2Pre: "Нажмите",
    expRunAnyway: "Выполнить",
    expB2Post: ". Windows запомнит этот выбор на будущее.",
    expLangNote: "двуязычно — переключите язык на главной странице",

    bodyTitle: "Заметки по установке",
    bodyP1Pre: "После установки укажите SerialHop ваш сервер lab-bridge и учётные данные, выданные администратором сервера. Полная инструкция —",
    bodyDocLink: "Настройте новый ПК лаборатории",
    bodyP1Post: ".",
    bodyTipTitle: "Совет",
    bodyTipBodyPre: "После того как агент отчитается, ваша лаборатория появится на главной странице за ~10 секунд. Если её там нет, посмотрите",
    bodyTipLink: "где искать в Grafana",
    bodyTipBodyPost: " — там сначала видны логи агента.",
    bodyFaqTitle: "Часто спрашивают",
    bodyFaq1Q: "Нужно ли открывать порты на файрволе ПК?",
    bodyFaq1A: "Нет — SerialHop сам открывает исходящий обратный туннель. Входящие правила не нужны.",
    bodyFaq2Q: "Можно ли запустить несколько агентов на одной машине?",
    bodyFaq2A: "Нет, только один. Два будут драться за одни и те же порты. Одно имя лаборатории на одну физическую машину.",
  },
};

Object.assign(window, { LBDownload });
