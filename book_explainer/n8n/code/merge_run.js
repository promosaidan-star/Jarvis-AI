// Merge every batch into explanations.json (+ run_metrics.json) and return the cards.
// A card's text is the verifier's corrected text; guard failures are attached, never hidden.
const fs = require('fs');
const batches = $input.all().map(i => i.json);
if (!batches.length) return [{ json: { error: 'no batches completed' } }];
const outDir = batches[0].outDir;
const explanations = {};
const cards = [];
for (const b of batches) {
  const ver = JSON.parse(fs.readFileSync(`${outDir}/verified_${b.k}.json`, 'utf8')).results || [];
  const pos = JSON.parse(fs.readFileSync(`${outDir}/batch_${b.k}.json`, 'utf8')).positions;
  for (const v of ver) {
    const p = pos.find(x => x.symbol === v.symbol) || {};
    const g = b.guard.cards?.[v.symbol] || { pass: false, fails: [{ check: 'guard_missing' }] };
    const card = {
      symbol: v.symbol, side: p.position > 0 ? 'long' : 'short', target_dollars: p.target_dollars,
      entry_date: p.entry_date, agg_z: p.entry?.agg_z, n_sources: p.entry?.n_sources,
      headline: v.corrected_headline, body: v.corrected_body, drivers: v.drivers, dissenters: v.dissenters,
      status_today: v.status_today, verify_problems: v.problems || [], verifier_ok: v.ok,
      guard_pass: g.pass, guard_fails: g.fails, company_fact_unsupported: g.company_fact_unsupported || [],
    };
    explanations[v.symbol] = card;
    cards.push(card);
  }
}
const n = cards.length || 1;
const sum = (f) => batches.reduce((a, b) => a + f(b), 0);
const metrics = {
  asof: batches[0].asof, model: batches[0].model, outDir, positions: cards.length,
  corrected_by_verifier: cards.filter(c => c.verifier_ok === false).length,
  guard_pass: cards.filter(c => c.guard_pass).length,
  tokens_in: sum(b => b.writer.in_tokens + b.verifier.in_tokens),
  tokens_out: sum(b => b.writer.out_tokens + b.verifier.out_tokens),
  seconds_llm: sum(b => b.writer.ms + b.verifier.ms) / 1000,
  per_position: {
    tokens_in: Math.round(sum(b => b.writer.in_tokens + b.verifier.in_tokens) / n),
    tokens_out: Math.round(sum(b => b.writer.out_tokens + b.verifier.out_tokens) / n),
    seconds: +(sum(b => b.writer.ms + b.verifier.ms) / 1000 / n).toFixed(2),
  },
  batches: batches.map(b => ({ k: b.k, symbols: b.symbols, writer: b.writer, verifier: b.verifier,
                               guard_pass: b.guard.n_pass, guard_n: b.guard.n, guard_error: b.guard.error })),
};
fs.writeFileSync(`${outDir}/explanations.json`, JSON.stringify(explanations, null, 1));
fs.writeFileSync(`${outDir}/run_metrics.json`, JSON.stringify(metrics, null, 1));
fs.writeFileSync('C:/Users/ajwal/Documents/ai_agent_eval/runs/LATEST.txt', outDir);
return [{ json: { metrics, cards } }];
