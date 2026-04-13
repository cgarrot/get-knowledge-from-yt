"use client";

import { forwardRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSlug from "rehype-slug";

export const MarkdownBody = forwardRef<
  HTMLElement,
  { content: string }
>(function MarkdownBody({ content }, ref) {
  return (
    <article
      ref={ref}
      className="markdown-body max-w-prose mx-auto text-base leading-relaxed space-y-4 text-foreground
      [&_h1]:text-2xl [&_h1]:font-semibold [&_h1]:pt-4 [&_h1]:scroll-mt-24
      [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:pt-3 [&_h2]:scroll-mt-24
      [&_h3]:text-lg [&_h3]:font-medium [&_h3]:pt-2 [&_h3]:scroll-mt-24
      [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5
      [&_code]:font-mono [&_code]:text-[0.9em] [&_code]:bg-black/5 dark:[&_code]:bg-white/10 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded
      [&_pre]:bg-black/5 dark:[&_pre]:bg-white/10 [&_pre]:p-3 [&_pre]:rounded-lg [&_pre]:overflow-x-auto
      [&_a]:text-sky-600 dark:[&_a]:text-sky-400 [&_a]:underline
      [&_blockquote]:border-l-2 [&_blockquote]:border-foreground/30 [&_blockquote]:pl-3 [&_blockquote]:italic
      [&_p]:text-foreground/90"
 >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSlug]}
      >
        {content}
      </ReactMarkdown>
    </article>
  );
});
