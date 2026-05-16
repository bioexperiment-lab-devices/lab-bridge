import { FlashStats } from "../types";

export function StatsCard({ stats }: { stats: FlashStats }) {
  const denom = stats.total || 0;
  const pct = denom > 0 ? Math.round((stats.successes / denom) * 100) : null;
  return (
    <div className="stats-card">
      <dl>
        <dt>Total flashes</dt><dd>{stats.total}</dd>
        <dt>Successes</dt><dd>{stats.successes}</dd>
        <dt>Rolled back</dt><dd>{stats.rollbacks}</dd>
        <dt>Failures</dt><dd>{stats.failures}</dd>
        <dt>Success rate</dt><dd>{pct === null ? "—" : `${pct}%`}</dd>
        <dt>Last flashed</dt>
        <dd>
          {stats.last_flashed_at
            ? `${stats.last_flashed_at} · ${stats.last_flashed_client} · ${stats.last_flashed_port}`
            : "—"}
        </dd>
      </dl>
    </div>
  );
}
