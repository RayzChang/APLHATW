import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'

const projectRoot = process.cwd()
const isWindows = process.platform === 'win32'
const hasNonAsciiPath = /[^\x00-\x7F]/.test(projectRoot)

const localTypeScriptBin = path.join(projectRoot, 'node_modules', 'typescript', 'bin', 'tsc')
const localViteBin = path.join(projectRoot, 'node_modules', 'vite', 'bin', 'vite.js')

function runNodeScript(scriptPath, args = [], cwd = projectRoot) {
  const result = spawnSync(process.execPath, [scriptPath, ...args], {
    cwd,
    stdio: 'inherit',
  })

  if (result.status !== 0) {
    process.exit(result.status ?? 1)
  }
}

function runCmd(command, args = []) {
  return spawnSync('cmd.exe', ['/c', command, ...args], {
    stdio: 'inherit',
  })
}

function pickDriveLetter() {
  const letters = ['X', 'Y', 'Z', 'W', 'V', 'U', 'T']
  return letters.find((letter) => !existsSync(`${letter}:\\`))
}

runNodeScript(localTypeScriptBin, ['-b'])

if (!isWindows || !hasNonAsciiPath) {
  runNodeScript(localViteBin, ['build'])
  process.exit(0)
}

const driveLetter = pickDriveLetter()

if (!driveLetter) {
  console.warn('No free drive letter was found. Falling back to direct vite build.')
  runNodeScript(localViteBin, ['build'])
  process.exit(0)
}

const mapResult = runCmd('subst', [`${driveLetter}:`, projectRoot])
if (mapResult.status !== 0) {
  console.warn(`Failed to map ${driveLetter}: to the project path. Falling back to direct vite build.`)
  runNodeScript(localViteBin, ['build'])
  process.exit(0)
}

try {
  const mappedRoot = `${driveLetter}:\\`
  const mappedViteBin = path.join(mappedRoot, 'node_modules', 'vite', 'bin', 'vite.js')
  runNodeScript(mappedViteBin, ['build'], mappedRoot)
} finally {
  runCmd('subst', [`${driveLetter}:`, '/d'])
}
