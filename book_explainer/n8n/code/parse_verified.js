// Parse verifier output -> verified_k.json (the guard node reads it from disk next).
const fs = require('fs');
const out = [];
for (const item of $input.all()) {
  const req = $('Parse draft').item.json;
  const r = item.json;
  const text = (r.candidates?.[0]?.content?.parts || []).map(p => p.text || '').join('');
  let ver;
  try {
    ver = JSON.parse(text.replace(/^```(json)?\s*|\s*```$/g, ''));
  } catch (e) {
    throw new Error(`verifier returned non-JSON for batch ${req.k}: ${text.slice(0, 300)}`);
  }
  if (Array.isArray(ver)) ver = { results: ver };
  fs.writeFileSync(`${req.outDir}/verified_${req.k}.json`, JSON.stringify(ver, null, 1));
  const u = r.usageMetadata || {};
  const results = ver.results || [];
  out.push({
    json: {
      k: req.k, outDir: req.outDir, asof: req.asof, model: req.model, symbols: req.symbols,
      writer: req.writer,
      verifier: { ms: Date.now() - req.t_verifier_start, in_tokens: u.promptTokenCount || 0,
                  out_tokens: (u.candidatesTokenCount || 0) + (u.thoughtsTokenCount || 0),
                  n_checked: results.length, n_corrected: results.filter(x => x.ok === false).length },
    },
  });
}
return out;
