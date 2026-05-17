import {
  Outlet,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { Shell } from "./Shell";
import { FlashTab } from "./tabs/FlashTab";
import { FirmwareTab } from "./tabs/FirmwareTab";
import { BackupsTab } from "./tabs/BackupsTab";
import { LogsTab } from "./tabs/LogsTab";
import { FlashFilters } from "./types";

// Root: branded topbar + outlet.
const rootRoute = createRootRoute({
  component: () => (
    <Shell>
      <Outlet />
    </Shell>
  ),
});

const flashRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => <FlashTab />,
});

const firmwareRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/firmware",
  component: () => <FirmwareTab selectedId={null} />,
});

const firmwareDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/firmware/$id",
  component: () => {
    const { id } = firmwareDetailRoute.useParams();
    return <FirmwareTab selectedId={id} />;
  },
});

const backupsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/backups",
  component: () => <BackupsTab selectedId={null} />,
});

const backupsDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/backups/$id",
  component: () => {
    const { id } = backupsDetailRoute.useParams();
    return <BackupsTab selectedId={id} />;
  },
});

// Logs search params shape: encodes both filters and the open drawer id.
interface LogsSearch {
  client?: string[];
  outcome?: string[];
  source_kind?: "firmware" | "backup";
  source_id?: string;
  since?: string;
  until?: string;
  open?: string;
}

function parseLogsSearch(raw: Record<string, unknown>): LogsSearch {
  const out: LogsSearch = {};
  if (Array.isArray(raw.client)) out.client = raw.client.filter(v => typeof v === "string") as string[];
  else if (typeof raw.client === "string") out.client = [raw.client];
  if (Array.isArray(raw.outcome)) out.outcome = raw.outcome.filter(v => typeof v === "string") as string[];
  else if (typeof raw.outcome === "string") out.outcome = [raw.outcome];
  if (raw.source_kind === "firmware" || raw.source_kind === "backup") out.source_kind = raw.source_kind;
  if (typeof raw.source_id === "string") out.source_id = raw.source_id;
  if (typeof raw.since === "string") out.since = raw.since;
  if (typeof raw.until === "string") out.until = raw.until;
  if (typeof raw.open === "string") out.open = raw.open;
  return out;
}

const logsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/logs",
  validateSearch: parseLogsSearch,
  component: () => {
    const search = logsRoute.useSearch();
    const filters: FlashFilters = {
      client: search.client,
      outcome: search.outcome,
      source_kind: search.source_kind,
      source_id: search.source_id,
      since: search.since,
      until: search.until,
    };
    return <LogsTab filters={filters} openId={search.open ?? null} />;
  },
});

const routeTree = rootRoute.addChildren([
  flashRoute,
  firmwareRoute,
  firmwareDetailRoute,
  backupsRoute,
  backupsDetailRoute,
  logsRoute,
]);

export const router = createRouter({
  routeTree,
  basepath: "/flash",
  defaultPreload: "intent",
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

export {
  flashRoute,
  firmwareRoute,
  firmwareDetailRoute,
  backupsRoute,
  backupsDetailRoute,
  logsRoute,
};
