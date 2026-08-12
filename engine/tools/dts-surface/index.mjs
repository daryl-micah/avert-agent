/* Emits the public .d.ts surface used by avert.detect.sdk_diff.ts_surface. */
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const root = process.argv[2];
if (!root) throw new Error("usage: node index.mjs <artifact-dir>");
const files = [];
function walk(dir) {
  for (const entry of fs.readdirSync(dir, {withFileTypes: true})) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full);
    else if (entry.name.endsWith(".d.ts")) files.push(full);
  }
}
walk(root);
const result = [];
function visit(node, prefix) {
  const named = node.name && ts.isIdentifier(node.name) ? node.name.text : null;
  const memberPrefix = named ? (prefix ? `${prefix}.${named}` : named) : prefix;
  if ((ts.isFunctionDeclaration(node) || ts.isMethodDeclaration(node)) && named && !named.startsWith("_")) {
    const params = node.parameters.map(p => p.type ? p.type.getText() : "any").join(",");
    const returns = node.type ? node.type.getText() : "any";
    result.push({path: memberPrefix, kind: ts.isMethodDeclaration(node) ? "method" : "function", signature: `(${params})->${returns}`, required: node.parameters.some(p => !p.questionToken && !p.initializer)});
  } else if ((ts.isClassDeclaration(node) || ts.isInterfaceDeclaration(node)) && named && !named.startsWith("_")) {
    result.push({path: memberPrefix, kind: ts.isClassDeclaration(node) ? "class" : "interface", signature: "", required: null});
  }
  ts.forEachChild(node, child => visit(child, memberPrefix));
}
for (const file of files) visit(ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true), "");
console.log(JSON.stringify(result));
