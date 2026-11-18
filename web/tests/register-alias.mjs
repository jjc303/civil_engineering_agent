import { existsSync } from 'node:fs'
import { registerHooks } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const srcRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../src')

function resolveWithTs(candidate) {
  if (existsSync(candidate)) return pathToFileURL(candidate).href
  if (existsSync(`${candidate}.ts`)) return pathToFileURL(`${candidate}.ts`).href
  if (existsSync(`${candidate}/index.ts`)) return pathToFileURL(`${candidate}/index.ts`).href
  return null
}

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('@/')) {
      const target = resolveWithTs(resolve(srcRoot, specifier.slice(2)))
      if (target) return { shortCircuit: true, url: target }
    }
    if ((specifier.startsWith('./') || specifier.startsWith('../')) && context.parentURL?.startsWith('file:')) {
      const baseDir = dirname(fileURLToPath(context.parentURL))
      if (!specifier.endsWith('.ts') && !specifier.endsWith('.js') && !specifier.endsWith('.mjs')) {
        const target = resolveWithTs(resolve(baseDir, specifier))
        if (target) return { shortCircuit: true, url: target }
      }
    }
    return nextResolve(specifier, context)
  },
})
