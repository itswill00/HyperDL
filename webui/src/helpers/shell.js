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
        console.warn('Running without root bridge (dev mock mode):', cmd)
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

export async function openMediaFile(filePath) {
  if (!filePath) return
  const safePath = "'" + String(filePath).replace(/'/g, "'\\''") + "'"
  const cmd = `if [ -x /data/adb/modules/hyperdl/bin/libhyperdl.so ]; then /data/adb/modules/hyperdl/bin/libhyperdl.so open ${safePath}; elif [ -x /data/adb/modules/hyperdl/system/bin/libhyperdl.so ]; then /data/adb/modules/hyperdl/system/bin/libhyperdl.so open ${safePath}; elif [ -x /data/adb/modules_update/hyperdl/bin/libhyperdl.so ]; then /data/adb/modules_update/hyperdl/bin/libhyperdl.so open ${safePath}; elif [ -x /data/adb/modules_update/hyperdl/system/bin/libhyperdl.so ]; then /data/adb/modules_update/hyperdl/system/bin/libhyperdl.so open ${safePath}; elif [ -x /system/bin/libhyperdl.so ]; then /system/bin/libhyperdl.so open ${safePath}; elif [ -x /data/data/com.termux/files/home/HyperDL_Module/bin/libhyperdl.so ]; then /data/data/com.termux/files/home/HyperDL_Module/bin/libhyperdl.so open ${safePath}; elif [ -x /data/data/com.termux/files/home/HyperDL_Module/system/bin/libhyperdl.so ]; then /data/data/com.termux/files/home/HyperDL_Module/system/bin/libhyperdl.so open ${safePath}; fi`
  try {
    return await execCommand(cmd, 10000)
  } catch (e) {
    console.error('Failed to open media:', e)
  }
}

export async function openFolder() {
  const cmd = `if [ -x /data/adb/modules/hyperdl/bin/libhyperdl.so ]; then /data/adb/modules/hyperdl/bin/libhyperdl.so open_folder; elif [ -x /data/adb/modules/hyperdl/system/bin/libhyperdl.so ]; then /data/adb/modules/hyperdl/system/bin/libhyperdl.so open_folder; elif [ -x /data/adb/modules_update/hyperdl/bin/libhyperdl.so ]; then /data/adb/modules_update/hyperdl/bin/libhyperdl.so open_folder; elif [ -x /data/adb/modules_update/hyperdl/system/bin/libhyperdl.so ]; then /data/adb/modules_update/hyperdl/system/bin/libhyperdl.so open_folder; elif [ -x /system/bin/libhyperdl.so ]; then /system/bin/libhyperdl.so open_folder; elif [ -x /data/data/com.termux/files/home/HyperDL_Module/bin/libhyperdl.so ]; then /data/data/com.termux/files/home/HyperDL_Module/bin/libhyperdl.so open_folder; elif [ -x /data/data/com.termux/files/home/HyperDL_Module/system/bin/libhyperdl.so ]; then /data/data/com.termux/files/home/HyperDL_Module/system/bin/libhyperdl.so open_folder; fi`
  try {
    return await execCommand(cmd, 10000)
  } catch (e) {
    console.error('Failed to open folder:', e)
  }
}

