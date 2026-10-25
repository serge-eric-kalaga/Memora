/** Remove only model-internal citation groups, never prose or domain identifiers. */
export function readableChatAnswer(answer: string): string {
  return answer
    .replace(/[ \t]*[([]\s*u\d+(?:\s*[,;]\s*u\d+)*\s*[)\]]/gi, "")
    .trim();
}
