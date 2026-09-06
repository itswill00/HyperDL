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
      /* Fallback for local browser dev */
      fetch('/api/exec', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmd })
      })
      .then(res => res.text())
      .then(resolve)
      .catch(() => {
        console.warn('Running without root bridge (dev mock mode):', cmd)
        resolve('')
      })
    }
  })
}

export function isKSU() {
  return typeof ksu !== 'undefined'
}

export function isRootBridgeAvailable() {
  return typeof ksu !== 'undefined' || typeof exec === 'function'
}

export async function openMediaFile(filePath) {
  if (!filePath) return
  const safePath = filePath.replace(/"/g, '\\"')
  try {
    const mime = filePath.endsWith('.mp3') ? 'audio/*' : 'video/*'
    await execCommand(`am start -a android.intent.action.VIEW -d "file://${safePath}" -t "${mime}" --grant-read-uri-permission 2>&1`)
  } catch (e) {
    console.error('Failed to open media:', e)
  }
}

export async function openFolder(folderPath = '/storage/emulated/0/Download/HyperDL') {
  try {
    await execCommand(`am start -a android.intent.action.VIEW -d "content://com.android.externalstorage.documents/document/primary%3ADownload%2FHyperDL" -t "resource/folder" 2>&1`)
  } catch (e) {
    console.error('Failed to open folder:', e)
  }
}
