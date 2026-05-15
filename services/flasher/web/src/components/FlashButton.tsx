interface Props {
  enabled: boolean
  clientName: string
  onClick: () => void
}

export function FlashButton({ enabled, clientName, onClick }: Props) {
  return (
    <section className="flash-button">
      <button type="button" disabled={!enabled} onClick={onClick}>
        Disconnect devices and flash
      </button>
      <p className="muted-text">
        This kicks any active session off the bus on <code>{clientName}</code>.
      </p>
    </section>
  )
}
