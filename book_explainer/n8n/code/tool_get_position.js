// Tool: get_position(symbol) -> the verified explanation card plus the numbers it was checked against.
// Reads the book payload written by eval/book_cli.py (results/book_latest.json). No prices, no account.
const fs = require('fs');
const book = JSON.parse(fs.readFileSync('C:/Users/ajwal/Documents/ai_agent_eval/results/book_latest.json', 'utf8'));
const sym = String(query || '').toUpperCase().replace(/[^A-Z.\-]/g, '');
const p = book.positions.find(x => x.symbol === sym);
if (!p) {
  const refused = book.refused_shorts.includes(sym) ? ` ${sym} was a refused short (not borrowable), so it is not held.` : '';
  return `NOT_IN_BOOK: ${sym || '(empty)'} is not a position in the ${book.asof} paper book.${refused} Positions: ${book.positions.map(x => x.symbol).join(', ')}`;
}
return JSON.stringify({
  asof: book.asof, symbol: p.symbol, name: p.name, sector: p.sector, side: p.side,
  target_dollars: p.target_dollars, entry_date: p.entry_date, agg_z_at_entry: p.agg_z,
  n_sources_at_entry: p.n_sources, entry_score: p.entry_score, entry_percentile: p.entry_pct,
  latest_score: p.latest_score, latest_percentile: p.latest_pct, status_today: p.status_today,
  entry_votes_by_size: p.votes, drivers: p.card?.drivers, dissenters: p.card?.dissenters,
  headline: p.card?.headline, explanation: p.card?.body, news_headlines: p.news,
  checks: { verifier_corrected: p.verifier_ok === false, guard_pass: p.guard_pass },
});
