import { marked } from "marked";

const chunks = [];

process.stdin.setEncoding("utf8");

process.stdin.on("data", (chunk) => {
  chunks.push(chunk);
});

process.stdin.on("end", () => {
  const markdown = chunks.join("");

  marked.setOptions({
    gfm: true,
    breaks: false,
  });

  const html = marked.parse(markdown);
  process.stdout.write(html);
});
