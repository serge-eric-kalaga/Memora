export type TimedSegment = { id: string; start: number; end: number };

export function segmentAt<T extends TimedSegment>(
  segments: T[],
  time: number,
): T | undefined {
  if (!Number.isFinite(time) || time < 0) return;
  return segments.find(
    (segment) => segment.start <= time && time < segment.end,
  );
}

export function loopRange(segment: TimedSegment | undefined, duration: number) {
  if (!segment || !Number.isFinite(duration) || duration <= 0) return null;
  const start = Math.max(0, segment.start);
  const end = Math.min(duration, segment.end);
  return Number.isFinite(start) && Number.isFinite(end) && end - start >= 0.1
    ? { start, end }
    : null;
}

export function adjacentSegment<T extends TimedSegment>(
  segments: T[],
  time: number,
  direction: -1 | 1,
) {
  const current = segments.findIndex(
    (segment) => segment.start <= time && time < segment.end,
  );
  if (current >= 0) return segments[current + direction];
  return direction === 1
    ? segments.find((segment) => segment.start > time)
    : segments.findLast((segment) => segment.end <= time);
}
