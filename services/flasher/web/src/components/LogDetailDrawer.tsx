// services/flasher/web/src/components/LogDetailDrawer.tsx (stub — Task 8.4 replaces)
interface Props { flashId: string; onClose: () => void; }
export function LogDetailDrawer({ flashId, onClose }: Props) {
  return (
    <aside className="drawer">
      <header><h3>Flash {flashId.slice(0, 8)}</h3><button onClick={onClose}>Close</button></header>
      <p>(stub — full version in Task 8.4)</p>
    </aside>
  );
}
