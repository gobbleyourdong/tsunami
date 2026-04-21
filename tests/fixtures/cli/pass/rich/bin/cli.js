#!/usr/bin/env node
// Rich Node CLI with subcommands (simplified commander-style).
const args = process.argv.slice(2);
if (args[0] === "--help" || args[0] === "-h" || args.length === 0) {
  console.log("Usage: rich [command] [options]");
  console.log("");
  console.log("Commands:");
  console.log("  build     Build the project");
  console.log("  serve     Serve the built output");
  console.log("  test      Run test suite");
  console.log("");
  console.log("Options:");
  console.log("  --help    Show this help");
  process.exit(0);
}
console.log(`Command: ${args[0]}`);
