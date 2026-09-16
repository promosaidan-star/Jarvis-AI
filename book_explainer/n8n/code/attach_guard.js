// Attach the deterministic guard's verdict (stdout of guard_cli.py) to the batch record.
return $input.all().map(item => {
  const prev = $('Parse verified').item.json;
  let guard;
  try {
    guard = JSON.parse(item.json.stdout);
  } catch (e) {
    guard = { error: `guard failed: ${(item.json.stderr || item.json.stdout || '').slice(0, 400)}`, cards: {}, n_pass: 0, n: 0 };
  }
  return { json: { ...prev, guard } };
});
