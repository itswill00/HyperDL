let cbSeq = 0

export function execCommand(cmd, timeoutMs = 60000) {
  return new Promise((resolve, reject) => {
    if (typeof ksu !== 'undefined' && typeof ksu.exec === 'function') {
      const id = `_hdl_${++cbSeq}_${Date.now()}`

      const timer = setTimeout(() => {
        if (window[id]) {
          delete window[id]
          resolve('')
        }
      }, timeoutMs)

      window[id] = (errno, stdout, stderr) => {
        clearTimeout(timer)
        delete window[id]
        // Keep stderr when stdout is empty so a command that only explains
        // itself on stderr still reaches the caller instead of looking silent.
        resolve(stdout || stderr || '')
      }

      try {
        ksu.exec(cmd, '{}', id)
      } catch (e) {
        clearTimeout(timer)
        delete window[id]
        reject(e)
      }
    } else if (typeof exec === 'function') {
      exec(cmd)
        .then(r => resolve(typeof r === 'object' ? (r.stdout || r.stderr || '') : String(r)))
        .catch(reject)
    } else {
      fetch('/api/exec', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmd })
      })
      .then(res => res.text())
      .then(resolve)
      .catch(() => {
        resolve('')
      })
    }
  })
}

export function base64EncodeUtf8(str) {
  if (!str) return ''
  try {
    return btoa(unescape(encodeURIComponent(str)))
  } catch {
    return ''
  }
}

export function base64DecodeUtf8(str) {
  if (!str) return ''
  try {
    return decodeURIComponent(escape(atob(str)))
  } catch {
    return ''
  }
}

export function shellQuote(arg) {
  return "'" + String(arg).replace(/'/g, "'\\''") + "'"
}

const BRIDGES = [
  '/data/adb/modules/hyperdl/bin/libhyperdl.so',
  '/data/adb/modules/hyperdl/system/bin/libhyperdl.so',
  '/data/adb/modules_update/hyperdl/bin/libhyperdl.so',
  '/data/adb/modules_update/hyperdl/system/bin/libhyperdl.so',
  '/system/bin/libhyperdl.so'
]

// Only actions this module is allowed to dispatch from here. Anything else is
// rejected instead of being silently rewritten to `status`, which previously
// made every `open` call report a download status instead of opening a file.
const ALLOWED_ACTIONS = new Set(['open', 'open_folder'])

function bridgeCmd(action, arg = '') {
  if (!ALLOWED_ACTIONS.has(action)) {
    throw new Error(`Refusing to dispatch unsupported bridge action: ${action}`)
  }
  const safeAction = shellQuote(action)
  const parts = BRIDGES
    .map(b => `[ -x ${b} ] && exec ${b} ${safeAction}${arg ? ' ' + arg : ''}`)
    .join(' || ')
  return `(${parts}) || echo binary_not_found`
}

function parseBridgeResult(raw) {
  const text = String(raw || '').trim()
  if (!text) return { ok: false, error: 'empty_response' }
  if (text === 'binary_not_found') return { ok: false, error: 'binary_not_found' }
  try {
    const data = JSON.parse(text)
    if (data && typeof data === 'object' && 'success' in data) {
      return { ok: !!data.success, error: data.error || '', data }
    }
    return { ok: true, error: '', data }
  } catch (e) {
    return { ok: true, error: '', data: text }
  }
}

export async function openMediaFile(filePath) {
  if (!filePath) return { ok: false, error: 'missing_path' }
  try {
    const raw = await execCommand(bridgeCmd('open', shellQuote(filePath)), 10000)
    return parseBridgeResult(raw)
  } catch (e) {
    return { ok: false, error: String(e) }
  }
}

export async function openFolder() {
  try {
    const raw = await execCommand(bridgeCmd('open_folder'), 10000)
    return parseBridgeResult(raw)
  } catch (e) {
    return { ok: false, error: String(e) }
  }
}
