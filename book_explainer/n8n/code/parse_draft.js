// Parse writer output -> draft_k.json; build the verifier request for the same batch.
const fs = require('fs');
const out = [];
for (const item of $input.all()) {
  const req = $('Loop over batches').item.json;   // the batch this response belongs to
  const r = item.json;
  const text = (r.candidates?.[0]?.content?.parts || []).map(p => p.text || '').join('');
  let draft;
  try {
    draft = JSON.parse(text.replace(/^```(json)?\s*|\s*```$/g, ''));
  } catch (e) {
    throw new Error(`writer returned non-JSON for batch ${req.k}: ${text.slice(0, 300)}`);
  }
  if (Array.isArray(draft)) draft = { explanations: draft };
  fs.writeFileSync(`${req.outDir}/draft_${req.k}.json`, JSON.stringify(draft, null, 1));
  const u = r.usageMetadata || {};
  out.push({
    json: {
      ...req,
      draftJson: JSON.stringify(draft),
      writer: { ms: Date.now() - req.t_writer_start, in_tokens: u.promptTokenCount || 0,
                out_tokens: (u.candidatesTokenCount || 0) + (u.thoughtsTokenCount || 0), n_cards: (draft.explanations || []).length },
      verifierUser: `=== glossary.json ===\n${req.glossaryForVerifier}\n\n=== batch_${req.k}.json ===\n${req.batchJson}\n\n=== draft_${req.k}.json ===\n${JSON.stringify(draft)}`,
      t_verifier_start: Date.now(),
    },
  });
}
return out;
