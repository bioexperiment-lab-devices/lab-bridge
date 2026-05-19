// Lab Bridge — Docs page (MkDocs Material-inspired)
/* global React, LB_ICONS */

function LBDocs({ lang = "en" }) {
  return (
    <div className="lb-docs-shell">
      <DocsSidebar lang={lang} />
      <div className="lb-docs-content">
        <DocsArticle lang={lang} />
      </div>
    </div>
  );
}

// ============================================================
// Sidebar — auto-built from folder structure
// ============================================================
function DocsSidebar({ lang }) {
  return (
    <aside className="lb-docs-side" aria-label="Documentation navigation">
      <div className="lb-docs-side__brand">
        <span style={{ color: "var(--accent)" }}>{LB_ICONS.docs}</span>
        <span style={{ flex: 1 }}>Documentation</span>
      </div>

      <a className="lb-docs-side__item" href="/docs/">Welcome</a>

      <div className="lb-docs-side__group">Researchers</div>
      <a className="lb-docs-side__item" data-level="1" href="#">Run your first notebook</a>
      <a className="lb-docs-side__item" data-level="1" href="#">Addressing a lab device</a>
      <a className="lb-docs-side__item" data-level="1" href="#">Working with results</a>

      <div className="lb-docs-side__group">Lab operators</div>
      <a className="lb-docs-side__item" data-folder="open" href="#">SerialHop agent</a>
      <a className="lb-docs-side__item" data-level="2" data-active="true" href="#">
        Connecting a device
        <span className="lb-docs-side__ru">RU</span>
      </a>
      <a className="lb-docs-side__item" data-level="2" href="#">Reading agent logs</a>
      <a className="lb-docs-side__item" data-level="2" href="#">Troubleshooting</a>
      <a className="lb-docs-side__item" data-level="1" href="#">Set up a new lab PC <span className="lb-docs-side__ru">RU</span></a>
      <a className="lb-docs-side__item" data-level="1" href="#">Where to look in Grafana</a>

      <div className="lb-docs-side__group">Server admins</div>
      <a className="lb-docs-side__item" data-level="1" href="#">Provisioning a client</a>
      <a className="lb-docs-side__item" data-level="1" href="#">Pushing firmware</a>

      <div className="lb-docs-side__group">Reference</div>
      <a className="lb-docs-side__item" data-level="1" href="#">FAQ</a>
      <a className="lb-docs-side__item" data-level="1" href="#">Glossary <span className="lb-docs-side__ru">RU</span></a>
    </aside>
  );
}

// ============================================================
// Article body — demonstrates every Markdown primitive
// ============================================================
function DocsArticle({ lang }) {
  const [copied, setCopied] = React.useState(false);

  return (
    <article className="lb-docs-article">
      <div className="lb-docs-article__crumbs">
        <a href="/docs/">Docs</a><span>/</span>
        <a href="#">Lab operators</a><span>/</span>
        <a href="#">SerialHop agent</a><span>/</span>
        Connecting a device
      </div>

      <header className="lb-docs-article__header">
        <h1>Connecting a device</h1>
        <div className="lb-lang" role="group" aria-label="Language">
          <button data-active={lang === "en" || undefined}>EN</button>
          <button data-active={lang === "ru" || undefined}>RU</button>
        </div>
      </header>

      <p>
        Once SerialHop is installed on a lab PC, each physical instrument needs
        a stable <em>client name</em> and the COM port it is wired to. Both are
        set in <code>C:/ProgramData/SerialHop/config.toml</code> — or interactively
        from the SerialHop operator panel — and the lab-bridge server will start
        offering the device under that name to every notebook a few seconds later.
      </p>

      <h2>
        Before you start <a className="lb-anchor" href="#before" aria-label="permalink">#</a>
      </h2>

      <ul>
        <li>SerialHop service is running and the <b>Server</b> lamp is green.</li>
        <li>You know the COM port your instrument is wired to (see <a href="#">Finding the COM port</a>).</li>
        <li>You have admin rights on the lab PC.</li>
      </ul>

      <div className="lb-adm" data-kind="tip">
        <div className="lb-adm__ico">i</div>
        <div className="lb-adm__body">
          <p className="lb-adm__title">Tip</p>
          <p>Use kebab-case for client names — <code>microscope-1</code>, not <code>Microscope_1</code>. The notebook environment is case-sensitive and researchers paste these names straight into code.</p>
        </div>
      </div>

      <h2>
        Register the device <a className="lb-anchor" href="#register" aria-label="permalink">#</a>
      </h2>

      <p>
        Open the SerialHop panel from the system tray and switch to the <b>Devices</b> tab. Click <b>Add device</b> and fill in the form, or paste the snippet below into your config file directly:
      </p>

      <CodeBlock
        lang="toml"
        filename="config.toml"
        lines={[
          [{ t: 'c', v: '# Each [[devices]] block exposes one instrument to lab-bridge.' }],
          [{ t: 'p', v: '[[devices]]' }],
          [{ t: 'k', v: 'name   ' }, { t: 'v', v: ' = ' }, { t: 's', v: '"microscope-1"' }, { t: 'c', v: '   # name researchers will see' }],
          [{ t: 'k', v: 'port   ' }, { t: 'v', v: ' = ' }, { t: 's', v: '"COM3"' }],
          [{ t: 'k', v: 'kind   ' }, { t: 'v', v: ' = ' }, { t: 's', v: '"microscope"' }],
          [{ t: 'k', v: 'baud   ' }, { t: 'v', v: ' = ' }, { t: 'n', v: '115200' }],
          [{ t: 'k', v: 'timeout' }, { t: 'v', v: ' = ' }, { t: 'n', v: '2.5' }],
          [],
          [{ t: 'k', v: 'label  ' }, { t: 'v', v: ' = ' }, { t: 's', v: '"Bench 4 — confocal"' }, { t: 'c', v: '  # optional human label' }],
        ]}
        onCopy={() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }}
        copied={copied}
      />

      <h3>
        Multiple instruments on one PC <a className="lb-anchor" href="#multi" aria-label="permalink">#</a>
      </h3>

      <p>
        Repeat the <code>[[devices]]</code> block for every instrument; names
        must be unique across the whole lab-bridge deployment.
      </p>

      <div className="lb-adm" data-kind="warning">
        <div className="lb-adm__ico">!</div>
        <div className="lb-adm__body">
          <p className="lb-adm__title">Warning</p>
          <p>Renaming a device that researchers already use will silently break their notebooks the next time they run. Coordinate name changes with the team — or keep the old name as an alias.</p>
        </div>
      </div>

      <h2>
        Verify the connection <a className="lb-anchor" href="#verify" aria-label="permalink">#</a>
      </h2>

      <ol>
        <li>Reload the config: <code>serialhop config reload</code>.</li>
        <li>Check the new device appears on the <b>Devices</b> tab with a green dot.</li>
        <li>From a notebook, run <code>labbridge.probe("microscope-1")</code> and wait for the OK.</li>
      </ol>

      <h3>What the status indicators mean</h3>

      <div className="lb-docs-table-wrap">
        <table className="lb-docs-table">
          <thead>
            <tr>
              <th style={{ width: 110 }}>Indicator</th>
              <th style={{ width: 130 }}>State</th>
              <th>Meaning</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><span className="lb-dot" data-tone="green" /> green</td>
              <td><code>online</code></td>
              <td>SerialHop has probed the port and the device responded within timeout.</td>
            </tr>
            <tr>
              <td><span className="lb-dot" data-tone="yellow" /> yellow</td>
              <td><code>connecting</code></td>
              <td>Port is open, no successful probe yet. Common right after plugging the cable in.</td>
            </tr>
            <tr>
              <td><span className="lb-dot" data-tone="red" /> red</td>
              <td><code>offline</code></td>
              <td>Port could not be opened, or the device stopped responding. See the Logs tab.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="lb-adm" data-kind="note">
        <div className="lb-adm__ico">i</div>
        <div className="lb-adm__body">
          <p className="lb-adm__title">Note</p>
          <p>The lab-bridge server caches the last known state for 30 seconds — a brief disconnect won't immediately surface as <code>offline</code> on the home page.</p>
        </div>
      </div>

      <h2>
        Common problems <a className="lb-anchor" href="#problems" aria-label="permalink">#</a>
      </h2>

      <h3>The port is listed but the device never comes online</h3>

      <p>
        Either the cable is dead or the baud rate is wrong. Try a different USB
        port first — if the issue persists, watch the agent logs while you reload:
      </p>

      <CodeBlock
        lang="bash"
        filename=""
        lines={[
          [{ t: 'c', v: '# Tail the SerialHop service log while the device reconnects' }],
          [{ t: 'p', v: '> ' }, { t: 'v', v: 'serialhop logs follow ' }, { t: 's', v: '--device microscope-1' }],
        ]}
      />

      <div className="lb-adm" data-kind="caution">
        <div className="lb-adm__ico">×</div>
        <div className="lb-adm__body">
          <p className="lb-adm__title">Caution</p>
          <p>Never share the lab-bridge credentials file. Anyone with it can pose as your lab. Rotate via your server admin (<code>task secrets:rotate-client</code>) if you suspect a leak.</p>
        </div>
      </div>

      <div style={{ display: "flex", gap: 16, marginTop: 36, paddingTop: 20, borderTop: "1px solid var(--border)", fontSize: 13 }}>
        <a href="#" style={{ color: "var(--text-secondary)", textDecoration: "none", display: "flex", flexDirection: "column", gap: 2 }}>
          <span style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}>← Previous</span>
          <span style={{ color: "var(--accent)", fontWeight: 500 }}>SerialHop agent overview</span>
        </a>
        <div style={{ flex: 1 }} />
        <a href="#" style={{ color: "var(--text-secondary)", textDecoration: "none", display: "flex", flexDirection: "column", gap: 2, textAlign: "right" }}>
          <span style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-muted)", fontFamily: "'IBM Plex Mono', monospace" }}>Next →</span>
          <span style={{ color: "var(--accent)", fontWeight: 500 }}>Reading agent logs</span>
        </a>
      </div>
    </article>
  );
}

// ============================================================
// Code block with copy button + minimal token highlighting
// ============================================================
function CodeBlock({ lang = "toml", filename, lines = [], copied, onCopy }) {
  return (
    <div className="lb-code">
      <div className="lb-code__head">
        <span style={{ color: "#C7C3B5" }}>{lang}</span>
        {filename && <span style={{ color: "#6B6759" }}>· {filename}</span>}
        <button className="lb-code__copy" data-copied={copied || undefined} onClick={onCopy}>
          {copied ? <>✓ copied</> : <>{LB_ICONS.copy} copy</>}
        </button>
      </div>
      <pre>
        {lines.map((line, i) => (
          <React.Fragment key={i}>
            {line.length === 0 ? '\u00A0' : line.map((tok, j) => (
              <span key={j} className={`lb-tok-${tok.t}`}>{tok.v}</span>
            ))}
            {'\n'}
          </React.Fragment>
        ))}
      </pre>
    </div>
  );
}

Object.assign(window, { LBDocs });
