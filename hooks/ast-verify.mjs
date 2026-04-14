#!/usr/bin/env node
/**
 * AST-based verification for Rule Z Quality Audit claims.
 *
 * Uses TypeScript's built-in compiler (which is installed in any project
 * that ships TS) to parse JSX/TSX/JS/TS files and answer precise questions:
 *   - Is ComponentX wrapped in React.memo?
 *   - Is handlerY declared via useCallback at module/component scope?
 *   - Is CONSTANT_Z a module-scope const?
 *
 * This replaces the regex-based checks in quality-audit-verify.py with
 * structurally accurate ones.
 *
 * Usage:
 *   node ast-verify.mjs <task-json-file>
 *
 * The task JSON:
 *   {
 *     "files": ["abs/path/to/a.tsx", "abs/path/to/b.tsx"],
 *     "claims": {
 *       "memoized_components": ["TaskRow"],
 *       "usecallback_handlers": ["handleToggle"],
 *       "usememo_derivations": ["userNames"],
 *       "hoisted_style_constants": ["ROW_STYLE"]
 *     }
 *   }
 *
 * Output JSON:
 *   {
 *     "unverified": [ { "field": "memoized_components.TaskRow", "reason": "..." } ],
 *     "verified":  [ "memoized_components.TaskRow", ... ]
 *   }
 *
 * If TypeScript isn't installed locally, falls back to a regex check
 * (printed as "degraded": true).
 */
import { readFileSync, existsSync } from "node:fs";
import { pathToFileURL } from "node:url";
import process from "node:process";

async function loadTypescript() {
  // Search for TypeScript in likely locations:
  //   1. TS_PATH env var
  //   2. TS_PROJECT_ROOT/node_modules/typescript
  //   3. Walk up from CWD looking for node_modules/typescript
  //   4. Global require
  const candidates = [];
  if (process.env.TS_PATH) candidates.push(process.env.TS_PATH);
  if (process.env.TS_PROJECT_ROOT) {
    candidates.push(`${process.env.TS_PROJECT_ROOT}/node_modules/typescript/lib/typescript.js`);
  }
  // Walk up from cwd
  const { dirname: _d, resolve: _r } = await import("node:path");
  let cwd = process.cwd();
  for (let i = 0; i < 6; i++) {
    candidates.push(_r(cwd, "node_modules", "typescript", "lib", "typescript.js"));
    const parent = _d(cwd);
    if (parent === cwd) break;
    cwd = parent;
  }

  for (const p of candidates) {
    try {
      if (!existsSync(p)) continue;
      const mod = await import(pathToFileURL(p).href);
      return mod.default || mod;
    } catch { /* try next */ }
  }
  try {
    const mod = await import("typescript");
    return mod.default || mod;
  } catch {
    return null;
  }
}

function loadFiles(paths) {
  const out = {};
  for (const p of paths) {
    try {
      out[p] = readFileSync(p, "utf8");
    } catch {
      /* skip */
    }
  }
  return out;
}

// --------------------------------------------------------------- //
// AST walker — only works if TypeScript is available
// --------------------------------------------------------------- //
function verifyWithAst(ts, filesContent, claims) {
  const memoized = new Set();
  const useCallbacks = new Set();
  const useMemos = new Set();
  const moduleConsts = new Set();

  for (const [path, code] of Object.entries(filesContent)) {
    const sf = ts.createSourceFile(path, code, ts.ScriptTarget.ESNext, true, ts.ScriptKind.TSX);
    walk(sf);

    function walk(node) {
      // const NAME = React.memo(...) or const NAME = memo(...)
      if (ts.isVariableStatement(node)) {
        const decl = node.declarationList.declarations[0];
        if (decl?.name && ts.isIdentifier(decl.name)) {
          const name = decl.name.text;
          if (decl.initializer) {
            const init = decl.initializer;
            // React.memo(X) / memo(X)
            if (ts.isCallExpression(init)) {
              const callee = init.expression;
              const isReactMemo =
                (ts.isPropertyAccessExpression(callee) &&
                  ts.isIdentifier(callee.expression) && callee.expression.text === "React" &&
                  callee.name.text === "memo") ||
                (ts.isIdentifier(callee) && callee.text === "memo");
              const isUseCallback = ts.isIdentifier(callee) && callee.text === "useCallback";
              const isUseMemo = ts.isIdentifier(callee) && callee.text === "useMemo";
              if (isReactMemo) memoized.add(name);
              if (isUseCallback) useCallbacks.add(name);
              if (isUseMemo) useMemos.add(name);
            }
            // Module-scope object/array literal: const ROW_STYLE = { ... }
            if (isTopLevel(node) && (
              ts.isObjectLiteralExpression(init) || ts.isArrayLiteralExpression(init) ||
              ts.isNumericLiteral(init) || ts.isStringLiteral(init)
            )) {
              moduleConsts.add(name);
            }
          }
        }
      }

      // export const NAME = ...
      if (ts.isExportAssignment(node) || (ts.isVariableStatement(node) &&
          node.modifiers?.some(m => m.kind === ts.SyntaxKind.ExportKeyword))) {
        // already handled above
      }

      // function FOO() wrapped later with React.memo(FOO) — detect via call args
      if (ts.isCallExpression(node)) {
        const callee = node.expression;
        const isReactMemo =
          (ts.isPropertyAccessExpression(callee) &&
            ts.isIdentifier(callee.expression) && callee.expression.text === "React" &&
            callee.name.text === "memo") ||
          (ts.isIdentifier(callee) && callee.text === "memo");
        if (isReactMemo && node.arguments[0]) {
          const arg = node.arguments[0];
          if (ts.isIdentifier(arg)) memoized.add(arg.text);
          if (ts.isFunctionExpression(arg) && arg.name) memoized.add(arg.name.text);
        }
      }

      ts.forEachChild(node, walk);
    }

    function isTopLevel(node) {
      // A VariableStatement at the top of SourceFile or directly inside a Module/Namespace block
      return node.parent && (ts.isSourceFile(node.parent) || ts.isModuleBlock(node.parent));
    }
  }

  return { memoized, useCallbacks, useMemos, moduleConsts };
}

// --------------------------------------------------------------- //
// Regex fallback
// --------------------------------------------------------------- //
function verifyWithRegex(filesContent) {
  const all = Object.values(filesContent).join("\n\n");
  const memoized = new Set();
  // Catch both `React.memo(Name)` AND `const Name = React.memo(Inner)`
  for (const m of all.matchAll(/(?:React\.)?memo\s*\(\s*(\w+)/g)) memoized.add(m[1]);
  for (const m of all.matchAll(/const\s+(\w+)\s*=\s*(?:React\.)?memo\s*\(/g)) memoized.add(m[1]);
  // Also `export const Name = React.memo(...)`
  for (const m of all.matchAll(/export\s+const\s+(\w+)\s*=\s*(?:React\.)?memo\s*\(/g)) memoized.add(m[1]);

  const useCallbacks = new Set(
    [...all.matchAll(/const\s+(\w+)\s*=\s*useCallback\s*\(/g)].map(m => m[1])
  );
  const useMemos = new Set(
    [...all.matchAll(/const\s+(\w+)\s*=\s*useMemo\s*\(/g)].map(m => m[1])
  );
  const moduleConsts = new Set(
    [...all.matchAll(/^(?:export\s+)?const\s+([A-Z_][A-Z0-9_]*)\s*[:=]/gm)].map(m => m[1])
  );
  return { memoized, useCallbacks, useMemos, moduleConsts };
}

// --------------------------------------------------------------- //
// Main
// --------------------------------------------------------------- //
async function main() {
  const taskFile = process.argv[2];
  if (!taskFile) {
    console.error("Usage: node ast-verify.mjs <task-json-file>");
    process.exit(1);
  }

  const task = JSON.parse(readFileSync(taskFile, "utf8"));
  const filesContent = loadFiles(task.files || []);

  if (Object.keys(filesContent).length === 0) {
    console.log(JSON.stringify({ unverified: [], verified: [], note: "no files to scan" }));
    return;
  }

  const ts = await loadTypescript();
  const degraded = !ts;
  const evidence = ts
    ? verifyWithAst(ts, filesContent, task.claims)
    : verifyWithRegex(filesContent);

  const unverified = [];
  const verified = [];

  for (const name of task.claims?.memoized_components || []) {
    const found = evidence.memoized.has(name);
    (found ? verified : unverified).push({
      field: `memoized_components.${name}`,
      reason: found ? "verified" : `no React.memo/memo wrap found for "${name}"`,
    });
  }
  for (const name of task.claims?.usecallback_handlers || []) {
    const found = evidence.useCallbacks.has(name);
    (found ? verified : unverified).push({
      field: `usecallback_handlers.${name}`,
      reason: found ? "verified" : `no "const ${name} = useCallback(" declaration found`,
    });
  }
  for (const name of task.claims?.usememo_derivations || []) {
    const found = evidence.useMemos.has(name);
    (found ? verified : unverified).push({
      field: `usememo_derivations.${name}`,
      reason: found ? "verified" : `no "const ${name} = useMemo(" declaration found`,
    });
  }
  for (const name of task.claims?.hoisted_style_constants || []) {
    const found = evidence.moduleConsts.has(name);
    (found ? verified : unverified).push({
      field: `hoisted_style_constants.${name}`,
      reason: found ? "verified" : `no module-scope "const ${name} = ..." found`,
    });
  }

  const result = {
    degraded,
    verified: verified.filter(v => v.reason === "verified").map(v => v.field),
    unverified: unverified.filter(u => u.reason !== "verified"),
  };
  console.log(JSON.stringify(result, null, 2));
}

main().catch(e => {
  console.error("ast-verify error:", e.message);
  process.exit(2);
});
