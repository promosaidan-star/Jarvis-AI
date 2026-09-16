// Tool: list_book() -> one line per position (symbol, side, target $, agg_z, sources, status today).
const fs = require('fs');
const book = JSON.parse(fs.readFileSync('C:/Users/ajwal/Documents/ai_agent_eval/results/book_latest.json', 'utf8'));
const rows = book.positions.map(p =>
  `${p.symbol} | ${p.name} | ${p.side} | $${p.target_dollars} | agg_z ${p.agg_z} | ${p.n_sources} sources | entered ${p.entry_date} | ${p.status_today}`);
return `Paper book as of ${book.asof} (${rows.length} positions; refused shorts: ${book.refused_shorts.join(', ')})\n` + rows.join('\n');
