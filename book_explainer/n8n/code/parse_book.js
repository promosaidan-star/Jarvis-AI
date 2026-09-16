// Parse book_cli.py stdout; cache it as results/book_latest.json (the Ask-the-book tools read that file).
const fs = require('fs');
const r = $input.first().json;
let book;
try {
  book = JSON.parse(r.stdout);
} catch (e) {
  throw new Error(`book_cli.py failed: ${(r.stderr || r.stdout || '').slice(0, 500)}`);
}
fs.writeFileSync('C:/Users/ajwal/Documents/ai_agent_eval/results/book_latest.json', JSON.stringify(book));
return [{ json: book }];
