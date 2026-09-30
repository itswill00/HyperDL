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

const BRIDGES = [
  '/data/adb/modules/hyperdl/bin/libhyperdl.so',
  '/data/adb/modules/hyperdl/system/bin/libhyperdl.so',
  '/data/adb/modules_update/hyperdl/bin/libhyperdl.so',
  '/data/adb/modules_update/hyperdl/system/bin/libhyperdl.so',
  '/system/bin/libhyperdl.so'
]
function bridgeCmd(action, arg = '') {
  const safeAction = action === 'open' || action === 'open_folder' ? action : 'status'
  const parts = BRIDGES.map(b => `[ -x ${b} ] && exec ${b} ${safeAction}${arg ? ' ' + arg : ''}`).join(' || ')
  return `(${parts})`
}

export async function openMediaFile(filePath) {
  if (!filePath) return
  const safePath = "'" + String(filePath).replace(/'/g, "'\\''") + "'"
  try { return await execCommand(bridgeCmd('open', safePath), 10000) }
  catch (e) { return '' }
}

export async function openFolder() {
  try { return await execCommand(bridgeCmd('open_folder'), 10000) }
  catch (e) { return '' }
}

