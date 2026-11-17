// Markdown を、Mermaid 図を描画した A4 の PDF にする。
// 使い方: node md2pdf.js <input.md> <output.pdf> [chromePath]
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const MarkdownIt = require("markdown-it");

const [, , input, output, chromeArg] = process.argv;
if (!input || !output) {
  console.error("usage: node md2pdf.js <input.md> <output.pdf> [chromePath]");
  process.exit(2);
}
const chrome =
  chromeArg || "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const toolDir = __dirname;
const src = fs.readFileSync(input, "utf8");

const md = new MarkdownIt({ html: true, linkify: false, typographer: false });
const defaultFence = md.renderer.rules.fence;
md.renderer.rules.fence = (tokens, idx, options, env, self) => {
  const token = tokens[idx];
  if ((token.info || "").trim() === "mermaid") {
    return `<pre class="mermaid">${md.utils.escapeHtml(token.content)}</pre>\n`;
  }
  return defaultFence(tokens, idx, options, env, self);
};

const body = md.render(src);
const title = path.basename(input, path.extname(input));
const css = `
@page { size: A4; margin: 14mm 13mm 16mm 13mm; }
* { box-sizing: border-box; }
html { font-size: 10pt; }
body {
  font-family: "Yu Gothic UI", "Yu Gothic", "Meiryo", "Segoe UI", sans-serif;
  color: #1b1b1b; line-height: 1.6; margin: 0;
}
h1 { font-size: 18pt; border-bottom: 3px solid #003894; color: #003894; padding-bottom: 4px; margin: 0 0 12px; }
h2 { font-size: 14pt; border-left: 6px solid #003894; padding: 2px 0 2px 8px; margin: 22px 0 8px; break-after: avoid; }
h3 { font-size: 11.5pt; color: #003894; margin: 16px 0 6px; break-after: avoid; }
h4 { font-size: 10.5pt; margin: 12px 0 4px; break-after: avoid; }
p, li { orphans: 2; widows: 2; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 10px; font-size: 9pt; break-inside: auto; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th, td { border: 1px solid #b9c3d6; padding: 4px 6px; vertical-align: top; text-align: left; }
th { background: #e8edf7; }
code { font-family: "Consolas", "BIZ UDGothic", monospace; font-size: 8.8pt; background: #f2f4f8; padding: 0 3px; border-radius: 3px; }
pre { background: #f5f7fb; border: 1px solid #d8dfeb; padding: 8px 10px; border-radius: 4px; overflow-wrap: anywhere; white-space: pre-wrap; break-inside: avoid; font-size: 8.6pt; }
pre code { background: none; padding: 0; }
pre.mermaid { background: #fff; border: 1px solid #d8dfeb; text-align: center; }
blockquote { border-left: 4px solid #9fb3d9; margin: 8px 0; padding: 4px 10px; background: #f6f8fc; color: #333; }
a { color: #003894; text-decoration: none; }
hr { border: 0; border-top: 1px solid #ccd3df; margin: 14px 0; }
img { max-width: 100%; }
`;

const html = `<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<title>${md.utils.escapeHtml(title)}</title>
<style>${css}</style>
<script src="${path.join(toolDir, "node_modules", "mermaid", "dist", "mermaid.min.js").replace(/\\/g, "/")}"></script>
</head><body>
${body}
<script>
  mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "default", flowchart: { htmlLabels: false } });
  mermaid.run({ querySelector: "pre.mermaid" }).catch(function (e) {
    document.body.setAttribute("data-mermaid-error", String(e && e.message || e));
  }).finally(function () { document.body.setAttribute("data-done", "1"); });
</script>
</body></html>`;

const htmlPath = path.join(toolDir, `_${path.basename(output, ".pdf")}.html`);
fs.writeFileSync(htmlPath, html, "utf8");
try {
  execFileSync(
    chrome,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-sandbox",
      "--no-pdf-header-footer",
      "--virtual-time-budget=30000",
      `--print-to-pdf=${path.resolve(output)}`,
      "file:///" + htmlPath.replace(/\\/g, "/"),
    ],
    { stdio: ["ignore", "ignore", "pipe"], timeout: 180000 }
  );
} finally {
  fs.unlinkSync(htmlPath);
}
console.log(`created ${path.resolve(output)}`);
