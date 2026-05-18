// Lab Bridge — Home page
// Header bar + intro + lab status + quick destinations + getting started.
// No announcements; status shows whole labs (not per-device).
/* global React, LB_ICONS */

function LBHome({ lang = "en" }) {
  const t = lang === "ru" ? STRINGS.ru : STRINGS.en;
  return (
    <div className="lb-page">
      <HomeHeader lang={lang} t={t} />
      <div className="lb-page__inner">
        <IntroSection t={t} />
        <div className="lb-status-row">
          <LabStatusPanel t={t} />
          <TopologyDiagram t={t} />
        </div>
        <QuickDestinations t={t} />
        <GettingStarted t={t} />
      </div>
    </div>
  );
}

// ============================================================
// Top header bar — thin, wordmark + language toggle
// ============================================================
function HomeHeader({ lang, t }) {
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
// Intro / about-the-platform — for first-time visitors.
// Modest footprint, informative not promotional.
// ============================================================
function IntroSection({ t }) {
  return (
    <section className="lb-intro-stmt" aria-label={t.aboutLabel}>
      <div className="lb-intro-stmt__eyebrow">
        <span className="lb-intro-stmt__eyebrow-tag">{t.eyebrowTag}</span>
      </div>
      <h2 className="lb-intro-stmt__headline">{t.statement}</h2>
      <div className="lb-intro-stmt__support">
        <p className="lb-intro-stmt__body">{t.aboutBody1}</p>
        <p className="lb-intro-stmt__body">{t.aboutBody2}</p>
      </div>
    </section>
  );
}

function TopologyDiagram({ t }) {
  return (
    <section className="lb-section lb-topo-section" aria-label={t.topoLabel}>
      <div className="lb-section__head">
        <h2 className="lb-section__title">{t.topoCaption}</h2>
        <div className="lb-section__rule" />
      </div>
      <div className="lb-topo">
        <div className="lb-topo__node">
          <div className="lb-topo__node-ico" aria-hidden="true">
            <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2.5" y="3.5" width="13" height="9" rx="1" />
              <path d="M2.5 11h13" />
              <path d="M6 15h6M7.5 12.5v2.5M10.5 12.5v2.5" />
            </svg>
          </div>
          <div className="lb-topo__node-body">
            <div className="lb-topo__node-title">{t.topoLabPC}</div>
            <div className="lb-topo__node-sub">{t.topoLabPCSub}</div>
          </div>
        </div>

        <div className="lb-topo__edge" aria-hidden="true">
          <span className="lb-topo__edge-label">{t.topoEdge1}</span>
        </div>

        <div className="lb-topo__node lb-topo__node--accent">
          <div className="lb-topo__node-ico" aria-hidden="true">
            <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4.5 11A3 3 0 016 5.2a4 4 0 017.7.7A2.8 2.8 0 0114 11" />
              <path d="M4.5 11h9" />
              <path d="M6 13.5h6M7.5 16h3" />
            </svg>
          </div>
          <div className="lb-topo__node-body">
            <div className="lb-topo__node-title">{t.topoServer}</div>
            <div className="lb-topo__node-sub">{t.topoServerSub}</div>
          </div>
        </div>

        <div className="lb-topo__edge" aria-hidden="true">
          <span className="lb-topo__edge-label">{t.topoEdge2}</span>
        </div>

        <div className="lb-topo__node">
          <div className="lb-topo__node-ico" aria-hidden="true">
            <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2.5" y="3.5" width="13" height="9" rx="1" />
              <path d="M2.5 6h13" />
              <circle cx="4.5" cy="4.75" r="0.4" fill="currentColor" />
              <circle cx="6.0" cy="4.75" r="0.4" fill="currentColor" />
              <path d="M5 9l1.5 1.5L5 12M8 12h3.5" />
              <path d="M6 15h6" />
            </svg>
          </div>
          <div className="lb-topo__node-body">
            <div className="lb-topo__node-title">{t.topoResearcher}</div>
            <div className="lb-topo__node-sub">{t.topoResearcherSub}</div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ============================================================
// Lab status panel — every registered lab + connection state
// ============================================================
const FLEET_LATEST = "v0.10.2";

const LABS = [
  // Offline first (problems get attention), then online.
  { name: "muller-group",  status: "offline", label: "Müller group · room 214",   version: "v0.10.2" },
  { name: "sequencer-rig", status: "offline", label: "Cold room · MinION rig",    version: "v0.9.3", outdated: true },
  { name: "bench-1",       status: "online",  label: "Bench 1",                   version: "v0.10.2" },
  { name: "bench-2",       status: "online",  label: "Bench 2 · incubator stack", version: "v0.10.2" },
  { name: "bench-4",       status: "online",  label: "Bench 4 · confocal + stir", version: "v0.10.2" },
  { name: "bench-6",       status: "online",  label: "Bench 6",                   version: "v0.10.0", outdated: true },
  { name: "bench-7",       status: "online",  label: "Bench 7 · fluorescence",    version: "v0.10.2" },
  { name: "fume-hood-1",   status: "online",  label: "Fume hood",                 version: "v0.10.2" },
  { name: "weighing-room", status: "online",  label: "Weighing room",             version: "v0.10.2" },
];

function LabStatusPanel({ t }) {
  const online  = LABS.filter(l => l.status === "online");
  const offline = LABS.filter(l => l.status === "offline");

  return (
    <section className="lb-section">
      <div className="lb-section__head">
        <h2 className="lb-section__title">{t.labsTitle}</h2>
        <div className="lb-section__rule" />
        <div className="lb-section__meta">{t.labsUpdated}</div>
      </div>
      <div className="lb-equip">
        <div className="lb-equip__head">
          <h2>{t.labsPanelTitle}</h2>
        </div>
        <LabChipGroup label={t.onlineLabel}  rows={online}  tone="green" t={t} />
        <LabChipGroup label={t.offlineLabel} rows={offline} tone="red"   t={t} />
      </div>
    </section>
  );
}

function LabChipGroup({ label, rows, tone, t }) {
  if (rows.length === 0) return null;
  return (
    <div className="lb-lablist" data-tone={tone}>
      <div className="lb-lablist__head">
        {label}
        <span className="lb-lablist__count">{rows.length}</span>
      </div>
      {rows.map((r) => (
        <div className="lb-labrow" data-tone={tone} data-outdated={r.outdated || undefined} key={r.name}>
          <span className="lb-dot" data-tone={tone} aria-hidden="true" />
          <code className="lb-labrow__name">{r.name}</code>
          {r.outdated && <span className="lb-labrow__pill" title={t.outdatedTooltip}>{t.outdated}</span>}
          <code className="lb-labrow__ver">{r.version}</code>
        </div>
      ))}
    </div>
  );
}

// ============================================================
// Quick destinations
// ============================================================
function QuickDestinations({ t }) {
  const cards = [
    { id: "jupyter",  title: "JupyterLab",   sub: "/jupyter/",            icon: LB_ICONS.jupyter,  primary: true,  ext: true },
    { id: "docs",     title: t.qdDocs,       sub: "/docs/",               icon: LB_ICONS.docs,     primary: false, ext: false },
    { id: "download", title: t.qdDownload,   sub: "/download/agent",      icon: LB_ICONS.download, primary: false, ext: false },
    { id: "grafana",  title: "Grafana",      sub: "/grafana/dashboards",  icon: LB_ICONS.grafana,  primary: false, ext: true },
  ];
  return (
    <section className="lb-section">
      <div className="lb-section__head">
        <h2 className="lb-section__title">{t.qdTitle}</h2>
        <div className="lb-section__rule" />
      </div>
      <div className="lb-quick">
        {cards.map((c) => (
          <a className="lb-quick-card" data-primary={c.primary || undefined} href={c.sub} key={c.id}>
            <div className="lb-quick-card__top">
              <span className="lb-quick-card__ico" aria-hidden="true">{c.icon}</span>
              <span className="lb-quick-card__title">{c.title}</span>
              <span className="lb-quick-card__arrow">{c.ext ? "↗" : "→"}</span>
            </div>
            <div className="lb-quick-card__sub">{c.sub}</div>
          </a>
        ))}
      </div>
    </section>
  );
}

// ============================================================
// Getting started
// ============================================================
function GettingStarted({ t }) {
  return (
    <section className="lb-section" style={{ marginBottom: 8 }}>
      <div className="lb-section__head">
        <h2 className="lb-section__title">{t.gsTitle}</h2>
        <div className="lb-section__rule" />
      </div>
      <div className="lb-start">
        <a className="lb-start-card" data-role="researcher" href="/docs/researcher/first-notebook">
          <span className="lb-start-card__role">{t.gsResearcher}</span>
          <span className="lb-start-card__title">{t.gsResearcherTitle}</span>
          <span className="lb-start-card__sub">{t.gsResearcherSub}</span>
          <span className="lb-start-card__path">/docs/researcher/first-notebook</span>
          <span className="lb-start-card__chev" aria-hidden="true">→</span>
        </a>
        <a className="lb-start-card" data-role="operator" href="/docs/operator/setup">
          <span className="lb-start-card__role">{t.gsOperator}</span>
          <span className="lb-start-card__title">{t.gsOperatorTitle}</span>
          <span className="lb-start-card__sub">{t.gsOperatorSub}</span>
          <span className="lb-start-card__path">/docs/operator/setup</span>
          <span className="lb-start-card__chev" aria-hidden="true">→</span>
        </a>
      </div>
    </section>
  );
}

// ============================================================
// Strings — EN and RU
// ============================================================
const STRINGS = {
  en: {
    idTag: "lab instrumentation platform",
    aboutLabel: "About lab-bridge",
    eyebrowTag: "What lab-bridge is",
    statement: "One bridge from every lab instrument to the researchers using it.",
    aboutBody1: "lab-bridge connects research labs to a shared cloud notebook environment. Lab instruments — pumps, valves, densitometers, thermostats — are wired by serial port to a lab PC running the SerialHop agent.",
    aboutBody2: "The agent opens a secure reverse tunnel that exposes those instruments to a JupyterLab server, so a researcher can drive an experiment from anywhere.",
    aboutForPrefix: "Built for",
    aboutFor: "research labs running serial-port instrumentation.",
    topoLabel: "How lab-bridge works — three labelled boxes",
    topoCaption: "How it works",
    topoLabPC: "Lab PC",
    topoLabPCSub: "devices + SerialHop",
    topoServer: "lab-bridge",
    topoServerSub: "reverse tunnels · auth · routing",
    topoResearcher: "JupyterLab",
    topoResearcherSub: "the researcher's notebook",
    topoEdge1: "reverse tunnel",
    topoEdge2: "named device API",

    labsTitle: "Lab status",
    labsPanelTitle: "Registered labs",
    labsUpdated: "updated 4s ago",
    online: "online", connecting: "connecting", offline: "offline",
    offlineLabel: "Offline",
    connectingLabel: "Connecting",
    onlineLabel: "Online",
    noLabel: "—",
    status: { online: "Online", offline: "Offline", connecting: "Connecting…" },
    outdated: "outdated",
    outdatedTooltip: "This lab is on an older SerialHop than the rest of the fleet",
    copyName: "Copy lab name",
    labsHint: "Per-device health (which pump is alive, which thermostat dropped off) lives in",
    labsHintLink: "Grafana →",

    qdTitle: "Quick destinations",
    qdDocs: "Browse docs",
    qdDownload: "Download agent",
    gsTitle: "Getting started",
    gsResearcher: "For researchers",
    gsResearcherTitle: "Run your first notebook",
    gsResearcherSub: "How to log into JupyterLab, address a lab by name, and run a first probe.",
    gsOperator: "For lab operators",
    gsOperatorTitle: "Set up a new lab PC",
    gsOperatorSub: "Install SerialHop, enter your issued credentials, and bring instruments online.",
  },
  ru: {
    idTag: "платформа для лабораторных приборов",
    aboutLabel: "О lab-bridge",
    eyebrowTag: "Что такое lab-bridge",
    statement: "Один мост от каждого прибора лаборатории к исследователям, которые с ним работают.",
    aboutBody1: "lab-bridge соединяет научные лаборатории с общей облачной средой ноутбуков. Лабораторные приборы — насосы, клапаны, денситометры, термостаты — подключены по последовательному порту к ПК лаборатории, на котором работает агент SerialHop.",
    aboutBody2: "Агент открывает защищённый обратный туннель, через который приборы видны серверу JupyterLab, и исследователь может управлять экспериментом откуда угодно.",
    aboutForPrefix: "Создано для",
    aboutFor: "научных лабораторий с приборами на последовательных портах.",
    topoLabel: "Как работает lab-bridge — три блока",
    topoCaption: "Как это работает",
    topoLabPC: "ПК лаборатории",
    topoLabPCSub: "приборы + SerialHop",
    topoServer: "lab-bridge",
    topoServerSub: "обратные туннели · авторизация · маршрутизация",
    topoResearcher: "JupyterLab",
    topoResearcherSub: "ноутбук исследователя",
    topoEdge1: "обратный туннель",
    topoEdge2: "API устройств",

    labsTitle: "Состояние лабораторий",
    labsPanelTitle: "Зарегистрированные лаборатории",
    labsUpdated: "обновлено 4 с назад",
    online: "онлайн", connecting: "подключение", offline: "не на связи",
    offlineLabel: "Не на связи",
    connectingLabel: "Подключение",
    onlineLabel: "Онлайн",
    noLabel: "—",
    status: { online: "Онлайн", offline: "Не на связи", connecting: "Подключение…" },
    outdated: "устар.",
    outdatedTooltip: "На этой лаборатории SerialHop старее, чем у остального флота",
    copyName: "Скопировать имя",
    labsHint: "Здоровье отдельных приборов (какой насос жив, какой термостат отключился) живёт в",
    labsHintLink: "Grafana →",

    qdTitle: "Быстрый доступ",
    qdDocs: "Документация",
    qdDownload: "Скачать агент",
    gsTitle: "Начало работы",
    gsResearcher: "Для исследователей",
    gsResearcherTitle: "Запустите свой первый ноутбук",
    gsResearcherSub: "Как войти в JupyterLab, обратиться к лаборатории по имени и запустить первую пробу.",
    gsOperator: "Для операторов лаборатории",
    gsOperatorTitle: "Настройте новый ПК лаборатории",
    gsOperatorSub: "Установите SerialHop, введите выданные учётные данные и подключите приборы.",
  },
};

Object.assign(window, { LBHome, __lbStrings: STRINGS });
