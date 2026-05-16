interface Props {
  skipBackup: boolean
  onSkipBackupChange: (skipBackup: boolean) => void
}

export function FlashOptions({ skipBackup, onSkipBackupChange }: Props) {
  return (
    <section className="step">
      <header>
        <h2>5. Options</h2>
      </header>
      <label className="switch">
        <input
          type="checkbox"
          checked={skipBackup}
          onChange={(e) => onSkipBackupChange(e.target.checked)}
        />
        Skip backup
      </label>
      {skipBackup ? (
        <p className="muted-text warning">
          ⚠ The device's existing flash will not be saved. There will be no
          way to restore the previous firmware from the lab machine if this
          flash needs to be rolled back.
        </p>
      ) : (
        <p className="muted-text">
          The current device flash will be captured to disk on the lab
          machine before erasing. Adds ~8 s.
        </p>
      )}
    </section>
  )
}
