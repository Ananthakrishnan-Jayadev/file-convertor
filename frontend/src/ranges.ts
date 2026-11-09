/** Page selections <-> range text like "1-3, 5, 8-". Pages are 1-based. */

const PART = /^(\d*)\s*-\s*(\d*)$|^(\d+)$/;

/** Sorted pages to the shortest range text: [1,2,3,5] -> "1-3, 5". */
export function toRanges(pages: Iterable<number>): string {
  const sorted = [...new Set(pages)].sort((a, b) => a - b);
  const parts: string[] = [];
  for (let i = 0; i < sorted.length; ) {
    let j = i;
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j] + 1) j++;
    parts.push(i === j ? `${sorted[i]}` : `${sorted[i]}-${sorted[j]}`);
    i = j + 1;
  }
  return parts.join(", ");
}

/** Range text to the set of pages it covers, or an error message. */
export function parseRanges(text: string, pageCount: number): { pages: Set<number> } | { error: string } {
  const pages = new Set<number>();
  for (const raw of text.split(",")) {
    const part = raw.trim();
    if (!part) continue;
    const m = PART.exec(part);
    if (!m) return { error: `"${part}" isn't a page or range. Use numbers like 3 or 2-5.` };
    const start = m[3] ? Number(m[3]) : m[1] ? Number(m[1]) : 1;
    const end = m[3] ? Number(m[3]) : m[2] ? Number(m[2]) : pageCount;
    if (start < 1 || end > pageCount) return { error: `"${part}" is outside this PDF, which has ${pageCount} pages.` };
    if (start > end) return { error: `"${part}" runs backwards. Write the lower page number first.` };
    for (let p = start; p <= end; p++) pages.add(p);
  }
  if (pages.size === 0) return { error: "Choose at least one page." };
  return { pages };
}
