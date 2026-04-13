/**
 * CLI module — public API barrel export.
 */

export { parseArgs, generateHTML, createManifest, addToManifest, validateManifest } from './runner'
export type { RunnerConfig, AssetManifest } from './runner'
