export function stripFrontmatter(md: string): string {
  const m = md.match(/^---\s*\n[\s\S]*?\n---\s*\n([\s\S]*)$/);
  return m ? m[1].trim() : md;
}
