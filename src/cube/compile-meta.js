// Compile a Cube model directory with Cube's own schema compiler and print the
// views as REST /meta-shaped JSON. Used by the schema compile test and by the
// eval's catalog builder. Usage: node compile-meta.js <modelDir>
const fs = require("fs");
const path = require("path");
const { prepareCompiler } = require(
  path.join(__dirname, "node_modules", "@cubejs-backend", "schema-compiler"),
);

function walk(dir) {
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .flatMap((e) =>
      e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)],
    );
}

async function main() {
  const modelDir = path.resolve(process.argv[2] || "model");
  const files = walk(modelDir)
    .filter((f) => /\.(yml|yaml|js)$/.test(f))
    .map((f) => ({
      fileName: path.relative(modelDir, f),
      content: fs.readFileSync(f, "utf8"),
    }));
  const repo = {
    localPath: () => modelDir,
    dataSchemaFiles: async () => files,
  };
  const { compiler, metaTransformer } = prepareCompiler(repo, {});
  await compiler.compile();
  const visible = (m) => m.isVisible !== false && m.public !== false;
  const member = (m) => ({
    name: m.name,
    title: m.title,
    type: m.type,
    description: m.description,
    meta: m.meta,
  });
  const cubes = metaTransformer.cubes
    .map((c) => c.config)
    .filter((c) => c.type === "view")
    .map((c) => ({
      name: c.name,
      title: c.title,
      type: c.type,
      description: c.description,
      meta: c.meta,
      measures: c.measures.filter(visible).map(member),
      dimensions: c.dimensions.filter(visible).map(member),
      segments: [],
    }));
  process.stdout.write(JSON.stringify({ cubes }));
}

main().catch((e) => {
  process.stderr.write(`compile failed: ${e.message}\n`);
  process.exit(1);
});
