/**
 * Normalize an arbitrary user-typed hex string into the canonical form
 * the API accepts: lowercase, no separators, no `0x` prefix.
 * Returns "" for empty / whitespace-only input.
 */
export function normalizeHex(input: string): string {
  return input
    .replace(/0x/gi, '')
    .replace(/[\s:_-]/g, '')
    .toLowerCase()
}

/** True iff the canonical hex string is non-empty, even-length, and 0-9a-f. */
export function isValidHex(canonical: string): boolean {
  return canonical.length > 0 && canonical.length % 2 === 0 && /^[0-9a-f]+$/.test(canonical)
}

/** Group a canonical hex string into 2-char bytes separated by spaces. */
export function formatHexBytes(canonical: string): string {
  const out: string[] = []
  for (let i = 0; i < canonical.length; i += 2) {
    out.push(canonical.slice(i, i + 2))
  }
  return out.join(' ')
}

/** Number of bytes the canonical hex string represents (0 if odd-length). */
export function hexByteCount(canonical: string): number {
  return Math.floor(canonical.length / 2)
}

/** Render canonical hex as an ASCII preview; non-printable bytes become "·". */
export function asciiPreview(canonical: string): string {
  const out: string[] = []
  for (let i = 0; i + 1 < canonical.length; i += 2) {
    const byte = parseInt(canonical.slice(i, i + 2), 16)
    if (Number.isNaN(byte)) {
      out.push('·')
    } else if (byte >= 0x20 && byte <= 0x7e) {
      out.push(String.fromCharCode(byte))
    } else {
      out.push('·')
    }
  }
  return out.join('')
}

/** Byte positions where two canonical hex strings of the same length differ. */
export function diffByteIndices(a: string, b: string): number[] {
  const out: number[] = []
  const n = Math.min(a.length, b.length) / 2
  for (let i = 0; i < n; i++) {
    if (a.slice(i * 2, i * 2 + 2) !== b.slice(i * 2, i * 2 + 2)) {
      out.push(i)
    }
  }
  // Any extra bytes in the longer string also count as mismatches.
  const longer = Math.max(a.length, b.length) / 2
  for (let i = n; i < longer; i++) out.push(i)
  return out
}
