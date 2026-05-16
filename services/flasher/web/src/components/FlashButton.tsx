interface Props {
  disabled: boolean
  onClick: () => void
}

export function FlashButton({ disabled, onClick }: Props) {
  return (
    <section className="flash-button">
      <button type="button" disabled={disabled} onClick={onClick}>
        Disconnect devices and flash
      </button>
    </section>
  )
}
