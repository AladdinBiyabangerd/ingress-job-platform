import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name === "node_modules" || e.name === ".next") continue;
      walk(p, out);
    } else if (/\.js$/.test(e.name)) out.push(p);
  }
  return out;
}

test("every <Component /> used in app/components is defined or imported", () => {
  const bad = [];
  for (const f of [...walk(path.join(root, "components")), ...walk(path.join(root, "app"))]) {
    const src = fs.readFileSync(f, "utf8");
    const used = new Set([...src.matchAll(/<([A-Z][A-Za-z0-9]*)[\s/>]/g)].map((m) => m[1]));
    for (const name of used) {
      const re = new RegExp(
        `(function\\s+${name}\\b|(const|let|class)\\s+${name}\\b|import\\s[^;]*\\b${name}\\b|[{,]\\s*${name}\\s*[,}])`,
      );
      if (!re.test(src)) bad.push(`${path.relative(root, f)}: <${name}>`);
    }
  }
  assert.deepEqual(bad, []);
});
