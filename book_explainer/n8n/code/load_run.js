// Load run: read the deterministic decomposition (glossary + batches) and set up an output dir.
// Input: webhook body {symbol?: "ABBV", run?: "run_2026-09-11", batches?: [0,1]} or manual trigger (full run).
// The LLM never sees prices, returns or the account: only glossary + batch JSON go forward.
const fs = require('fs');
const path = require('path');

const ROOT = 'C:/Users/ajwal/Documents/ai_agent_eval';
const MODEL = 'gemini-3.5-flash-lite';
const ADAPTER = `

## Runtime adapter (n8n)
You have no file tools in this runtime. The full contents of the files named above are
inlined in the user message between "=== <filename> ===" markers; treat them as the files.
Where the prompt says to write output to a file, return that JSON object as your ENTIRE
response instead (no prose, no code fences). Ignore any instruction to reply with a count.`;

const body = ($input.first().json.body) || {};
const srcRun = body.run || 'run_2026-09-11';
const srcDir = path.join(ROOT, srcRun);
const glossary = JSON.parse(fs.readFileSync(path.join(srcDir, 'glossary.json'), 'utf8'));
const writerPrompt = fs.readFileSync(path.join(srcDir, 'prompts', 'writer_prompt.md'), 'utf8');
const verifierPrompt = fs.readFileSync(path.join(srcDir, 'prompts', 'verifier_prompt.md'), 'utf8');

let batches = [];
for (let k = 0; fs.existsSync(path.join(srcDir, `batch_${k}.json`)); k++) {
  batches.push(JSON.parse(fs.readFileSync(path.join(srcDir, `batch_${k}.json`), 'utf8')).positions);
}
if (!batches.length) throw new Error(`no batch_k.json in ${srcDir}`);

const symbol = body.symbol ? String(body.symbol).toUpperCase().trim() : null;
if (symbol) {
  const pos = batches.flat().find(p => p.symbol === symbol);
  if (!pos) {
    return [{ json: { refused: true, message: `${symbol} is not a position in the ${glossary.asof} book.` } }];
  }
  batches = [[pos]];
} else if (Array.isArray(body.batches)) {
  batches = body.batches.map(k => batches[k]);
}

const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const outDir = path.join(ROOT, 'runs', `n8n_${glossary.asof}_${symbol || 'full'}_${stamp}`).replace(/\\/g, '/');
fs.mkdirSync(outDir, { recursive: true });
fs.copyFileSync(path.join(srcDir, 'glossary.json'), path.join(outDir, 'glossary.json'));

return batches.map((positions, k) => {
  fs.writeFileSync(path.join(outDir, `batch_${k}.json`), JSON.stringify({ positions }));
  // Only this batch's company backgrounds are inlined (the rest of the glossary is unchanged).
  const syms = new Set(positions.map(p => p.symbol));
  const g = { ...glossary, backgrounds: Object.fromEntries(Object.entries(glossary.backgrounds).filter(([s]) => syms.has(s))) };
  const files = `=== glossary.json ===\n${JSON.stringify(g)}\n\n=== batch_${k}.json ===\n${JSON.stringify({ positions })}`;
  return {
    json: {
      refused: false, k, outDir, model: MODEL, asof: glossary.asof, symbols: [...syms],
      writerSystem: writerPrompt.replaceAll('{S}', '.').replaceAll('{k}', String(k)) + ADAPTER,
      verifierSystem: verifierPrompt.replaceAll('{S}', '.').replaceAll('{k}', String(k)) + ADAPTER,
      files, glossaryForVerifier: JSON.stringify(g), batchJson: JSON.stringify({ positions }),
      t_writer_start: Date.now(),
    },
  };
});
