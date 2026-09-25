// Pure formatting / parsing helpers for the HyperDL WebUI.
// No Vue reactivity here — safe to unit test and reuse.

export const STANDARD_RESOLUTIONS = [
  { height: 2160, format_id: '2160', label: '2160p (4K Ultra HD)', badge: '4K', desc: 'Ultra HD', ext: 'mp4' },
  { height: 1440, format_id: '1440', label: '1440p (2K QHD)', badge: '2K', desc: 'Quad HD', ext: 'mp4' },
  { height: 1080, format_id: '1080', label: '1080p Full HD', badge: 'FHD', desc: 'Recommended', ext: 'mp4' },
  { height: 720, format_id: '720', label: '720p HD', badge: 'HD', desc: 'Fast & Crisp', ext: 'mp4' },
  { height: 480, format_id: '480', label: '480p SD', badge: 'SD', desc: 'Standard', ext: 'mp4' },
  { height: 360, format_id: '360', label: '360p Data Saver', badge: 'SD', desc: 'Data Saver', ext: 'mp4' }
]

export const SUPPORTED_PLATFORMS = [
  { id: 'tiktok', name: 'TikTok' },
  { id: 'instagram', name: 'Instagram' },
  { id: 'x', name: 'X' },
  { id: 'youtube', name: 'YouTube' },
  { id: 'facebook', name: 'Facebook' },
  { id: 'reddit', name: 'Reddit' },
  { id: 'pinterest', name: 'Pinterest' },
  { id: 'bluesky', name: 'Bluesky' },
  { id: 'threads', name: 'Threads' },
  { id: 'bilibili', name: 'Bilibili' },
  { id: 'streamable', name: 'Streamable' }
]

export function isNetworkError(err) {
  if (!err) return false
  const str = String(err).toLowerCase()
  return (
    str.includes('name resolution') ||
    str.includes('temporary failure') ||
    str.includes('no address associated') ||
    str.includes('unreachable') ||
    str.includes('refused') ||
    str.includes('timed out') ||
    str.includes('timeout') ||
    str.includes('gaierror') ||
    str.includes('getaddrinfo') ||
    str.includes('connection reset') ||
    str.includes('remotedisconnected') ||
    str.includes('networkerror') ||
    str.includes('urlopen error') ||
    str.includes('no internet connection')
  )
}

export function formatErrorMessage(err) {
  if (!err) return 'Unknown error occurred'
  if (isNetworkError(err)) {
    return 'No internet connection or network unreachable. Please check your Wi-Fi/data and retry.'
  }
  const str = String(err)
  const low = str.toLowerCase()
  if (low.includes('certificate_verify_failed') || (low.includes('ssl') && low.includes('verify'))) {
    return 'Network security error: SSL certificate verification failed. Check device date and time.'
  }
  if (str.includes('HTTP Error 403') || low.includes('forbidden')) {
    return 'Access blocked by platform (HTTP 403). Session cookies may be required.'
  }
  if (str.includes('HTTP Error 404') || low.includes('not found')) {
    return 'Media not found (HTTP 404). The link may be broken or deleted.'
  }
  return str
}

export function formatProgressInfo(t) {
  if (!t) return ''
  if (t.status === 'resolving') {
    return t.title || 'Connecting to source...'
  }
  if (t.status === 'paused') {
    return 'Download paused'
  }
  if (t.downloaded) {
    const tot = String(t.total || '').trim()
    if (tot && tot !== 'N/A' && tot !== 'NA' && tot !== 'None' && tot !== 'null' && tot !== '?') {
      return `${t.downloaded} / ${tot}`
    }
    return (t.percent && t.percent > 0) ? `${t.downloaded} (${t.percent}%)` : t.downloaded
  }
  return ''
}

export function formatSpeedInfo(t) {
  if (!t) return ''
  const spd = String(t.speed || '').trim()
  const eta = String(t.eta || '').trim()
  const hasSpeed = spd && spd !== 'N/A' && spd !== 'NA' && spd !== 'None' && spd !== 'null'
  const hasEta = eta && eta !== 'N/A' && eta !== 'NA' && eta !== 'None' && eta !== 'null'

  if (hasSpeed && hasEta) {
    return `${spd} • ETA ${eta}`
  }
  if (hasSpeed) {
    return spd
  }
  if (hasEta) {
    return `ETA ${eta}`
  }
  if (t.status === 'paused') {
    return `${t.percent || 0}% ready`
  }
  return ''
}

export function formatFileSize(bytes) {
  if (!bytes || bytes <= 0) return ''
  if (bytes >= 1024 * 1024 * 1024) return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB'
  if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(0) + ' MB'
  return (bytes / 1024).toFixed(0) + ' KB'
}

export function formatTruncatedUrl(u) {
  if (!u) return ''
  try {
    const parsed = new URL(u)
    const host = parsed.hostname.replace('www.', '')
    const path = parsed.pathname.length > 20 ? parsed.pathname.slice(0, 18) + '...' : parsed.pathname
    return `${host}${path}`
  } catch {
    return u.length > 35 ? u.slice(0, 32) + '...' : u
  }
}

export function isVideoExt(ext) {
  const e = (ext || '').toLowerCase()
  return ['mp4', 'mkv', 'webm', 'mov', 'avi', 'flv'].includes(e)
}

export function isImageExt(ext) {
  const e = (ext || '').toLowerCase()
  return ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'].includes(e)
}

export function isAudioExt(ext) {
  const e = (ext || '').toLowerCase()
  return ['mp3', 'm4a', 'aac', 'ogg', 'flac', 'wav', 'opus'].includes(e)
}

export function getExtIcon(ext) {
  const e = (ext || '').toLowerCase()
  if (['mp4', 'mkv', 'webm', 'mov', 'avi'].includes(e)) return 'video'
  if (['flac', 'wav', 'mp3', 'm4a', 'aac', 'ogg', 'opus'].includes(e)) return 'music'
  return 'image'
}

export function needsResolutionPicker(u) {
  const l = (u || '').toLowerCase()
  return l.includes('youtube.com') || l.includes('youtu.be')
}

export function shellEscape(arg) {
  return "'" + String(arg).replace(/'/g, "'\\''") + "'"
}

export function extractUrl(text) {
  if (!text) return ''
  const match = String(text).match(/https?:\/\/[^\s<>"]+/)
  const raw = match ? match[0].trim() : text.trim()
  if (!raw.startsWith('http://') && !raw.startsWith('https://')) return raw

  try {
    const parsed = new URL(raw)
    const params = new URLSearchParams(parsed.search)
    const host = parsed.hostname.toLowerCase()
    const isYt = host.includes('youtube.com') || host.includes('youtu.be')
    const isIg = host.includes('instagram.com')
    const isTt = host.includes('tiktok.com') || host.includes('douyin.com')
    const isX = host.includes('x.com') || host.includes('twitter.com')

    const toRemove = []
    for (const key of params.keys()) {
      const k = key.toLowerCase()
      if (k.startsWith('utm_') || k === 'ref' || k === 'ref_src') {
        toRemove.push(key)
      } else if ((k === 'si' || k === 'feature') && isYt) {
        toRemove.push(key)
      } else if (k === 'igsh' && isIg) {
        toRemove.push(key)
      } else if ((k === '_t' || k === '_r') && isTt) {
        toRemove.push(key)
      } else if ((k === 's' || (k === 't' && !isYt)) && isX) {
        toRemove.push(key)
      }
    }

    for (const key of toRemove) {
      params.delete(key)
    }

    parsed.search = params.toString() ? `?${params.toString()}` : ''
    return parsed.toString()
  } catch (e) {
    return raw
  }
}
