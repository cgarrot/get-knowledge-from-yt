"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownBody({ content }: { content: string }) {
  return (
    <article
      className="markdown-body text-sm leading-relaxed space-y-3 [&_h1]:text-xl [&_h1]:font-semibold [&_h1]:pt-2
      [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:pt-2
      [&_h3]:text-base [&_h3]:font-medium
      [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5
      [&_code]:font-mono [&_code]:text-xs [&_code]:bg-black/5 dark:[&_code]:bg-white/10 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded
      [&_pre]:bg-black/5 dark:[&_pre]:bg-white/10 [&_pre]:p-3 [&_pre]:rounded-lg [&_pre]:overflow-x-auto
      [&_a]:text-sky-600 dark:[&_a]:text-sky-400 [&_a]:underline
      [&_blockquote]:border-l-2 [&_blockquote]:border-foreground/30 [&_blockquote]:pl-3 [&_blockquote]:italic"
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </article>
  );
}
