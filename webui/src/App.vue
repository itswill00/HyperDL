<template>
  <div class="app-shell">
    
        <header class="page-header">
      <div>
        <div class="page-header-title">HyperDL</div>
        <div class="page-header-sub">Media downloader</div>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <span class="badge-pill" v-if="storageFree">
          {{ storageFree }} free
        </span>
        <span class="badge-pill active">
          v1.0.0
        </span>
      </div>
    </header>

        <div style="padding: 10px 16px 0 16px; background: var(--bg);">
      <div class="tabs-control">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'download' }"
          @click="activeTab = 'download'"
        >
          <Icons name="download" :size="14" />
          <span>Downloader</span>
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'cookies' }"
          @click="activeTab = 'cookies'"
        >
          <Icons name="settings" :size="14" />
          <span>Cookies</span>
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'console' }"
          @click="activeTab = 'console'"
        >
          <Icons name="info" :size="14" />
          <span>Console</span>
        </button>
      </div>
    </div>

        <main class="content-area">

            <div v-show="activeTab === 'download'">
        
                <section class="md3-card" style="margin-top: 4px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
            <span style="font-size: 13px; font-weight: 600; color: var(--on-surface);">New download</span>
            <span class="badge-pill" :class="{ active: detectedPlatform.name !== 'Direct link' }" style="font-size: 10px;">
              <Icons :name="detectedPlatform.id" :size="12" />
              <span>{{ detectedPlatform.name }}</span>
            </span>
          </div>

                    <div class="text-input-wrapper">
            <input
              type="url"
              class="text-input"
              v-model="url"
              placeholder="Paste media link here..."
              @keyup.enter="startDownload"
            />
            <button
              v-if="url"
              class="btn btn-icon"
              style="background: transparent; border: none; width: 28px; height: 28px;"
              @click="url = ''"
              title="Clear"
            >
              ✕
            </button>
            <button
              class="btn btn-secondary"
              style="padding: 6px 12px; font-size: 11px; margin-left: 4px;"
              @click="pasteClipboard"
            >
              <Icons name="clipboard" :size="13" />
              Paste
            </button>
          </div>

                    <div class="platform-chips-row">
            <div
              v-for="p in supportedPlatforms"
              :key="p.id"
              class="platform-chip"
              :class="{ active: detectedPlatform.id === p.id }"
            >
              <Icons :name="p.id" :size="12" />
              <span>{{ p.name }}</span>
            </div>
          </div>

                    <div style="margin-top: 14px;">
            <div style="font-size: 11px; color: var(--on-surface-variant); margin-bottom: 6px; font-weight: 500;">
              Format
            </div>
            <div class="chips-row">
              <div
                class="chip-item"
                :class="{ active: selectedFormat === 'video' }"
                @click="selectedFormat = 'video'"
              >
                <Icons name="video" :size="14" />
                <span>Video</span>
              </div>
              <div
                class="chip-item"
                :class="{ active: selectedFormat === 'audio' }"
                @click="selectedFormat = 'audio'"
              >
                <Icons name="music" :size="14" />
                <span>Audio</span>
              </div>
              <div
                class="chip-item"
                :class="{ active: selectedFormat === 'album' }"
                @click="selectedFormat = 'album'"
              >
                <Icons name="image" :size="14" />
                <span>Photos</span>
              </div>
            </div>
          </div>

                    <div style="margin-top: 16px;">
            <button
              class="btn btn-primary"
              style="width: 100%; height: 44px; font-size: 14px;"
              :disabled="!url.trim() || isProcessing"
              @click="startDownload"
            >
              <Icons :name="isProcessing ? 'refresh' : 'download'" :size="16" />
              <span>{{ isProcessing ? 'Downloading...' : 'Download' }}</span>
            </button>
          </div>
        </section>

                <section v-if="task.status !== 'idle'" class="md3-card" style="border-color: var(--primary);">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div class="icon-badge">
                <Icons :name="task.status === 'completed' ? 'check' : 'download'" :size="18" />
              </div>
              <div>
                <div style="font-size: 13px; font-weight: 600; color: var(--on-surface);">
                  {{ taskStatusTitle }}
                </div>
                <div style="font-size: 11px; color: var(--on-surface-variant); max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                  {{ task.title || url }}
                </div>
              </div>
            </div>
            <span class="badge-pill" :class="{ active: task.status === 'completed' }">
              {{ task.percent }}%
            </span>
          </div>

                    <div class="progress-track">
            <div class="progress-fill" :style="{ width: task.percent + '%' }"></div>
          </div>

                    <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--on-surface-variant); margin-top: 8px; font-family: var(--font-mono);">
            <span>{{ task.downloaded ? `${task.downloaded} / ${task.total}` : (task.status === 'resolving' ? (task.title || 'Connecting to source...') : '') }}</span>
            <span>{{ task.speed ? task.speed : '' }}</span>
          </div>

                    <div v-if="task.status === 'error'" style="margin-top: 10px; color: var(--error); font-size: 12px; background: var(--error-container); padding: 8px 12px; border-radius: 8px;">
            {{ task.error || 'Download failed' }}
          </div>

                    <div v-if="task.status === 'completed'" style="display: flex; gap: 8px; margin-top: 12px;">
            <button class="btn btn-primary" :disabled="openingPath === task.file_path" style="flex: 1; padding: 8px 12px; font-size: 12px;" @click="openMedia(task.file_path)">
              <Icons name="play" :size="14" />
              {{ openingPath === task.file_path ? 'Opening...' : 'Open media' }}
            </button>
            <button class="btn btn-secondary" :disabled="openingFolder" style="padding: 8px 12px; font-size: 12px;" @click="openMediaFolder">
              <Icons name="folder" :size="14" />
              {{ openingFolder ? 'Opening...' : 'Open folder' }}
            </button>
          </div>
        </section>

                <div class="section-title">Automation</div>
        <div class="md3-list-group">
          <div class="md3-list-row">
            <div style="display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1;">
              <div class="icon-badge secondary">
                <Icons name="clipboard" :size="18" />
              </div>
              <div>
                <div style="font-size: 13px; font-weight: 600; color: var(--on-surface);">Clipboard monitor</div>
                <div style="font-size: 11px; color: var(--on-surface-variant);">Download supported links automatically when copied</div>
              </div>
            </div>
            <label class="md3-switch">
              <input type="checkbox" :checked="autoDl" @change="toggleAutoDl" />
              <span class="md3-switch-track">
                <span class="md3-switch-thumb"></span>
              </span>
            </label>
          </div>

          <div class="md3-list-row clickable" @click="openMediaFolder">
            <div style="display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1;">
              <div class="icon-badge secondary">
                <Icons name="folder" :size="18" />
              </div>
              <div>
                <div style="font-size: 13px; font-weight: 600; color: var(--on-surface);">Destination folder</div>
                <div style="font-size: 11px; color: var(--on-surface-variant); font-family: var(--font-mono);">/Download/HyperDL</div>
              </div>
            </div>
            <Icons name="chevron-right" :size="16" style="color: var(--on-surface-variant);" />
          </div>
        </div>

                <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 18px; margin-bottom: 8px;">
          <div class="section-title" style="margin: 0;">Recent downloads ({{ historyList.length }})</div>
          <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px; gap: 4px;" @click="fetchHistory">
            <Icons name="refresh" :size="12" />
            Refresh
          </button>
        </div>

        <div class="md3-list-group" v-if="historyList.length > 0">
          <div
            v-for="item in historyList"
            :key="item.path"
            class="md3-list-row"
          >
            <div style="display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; cursor: pointer;" @click="openMedia(item.path)">
              <div class="icon-badge secondary">
                <Icons :name="getExtIcon(item.ext)" :size="16" />
              </div>
              <div style="min-width: 0; flex: 1;">
                <div style="font-size: 12px; font-weight: 600; color: var(--on-surface); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                  {{ item.name }}
                </div>
                <div style="font-size: 10px; color: var(--on-surface-variant); font-family: var(--font-mono); margin-top: 2px;">
                  {{ item.size }} · {{ (item.ext || '').toLowerCase() }}
                </div>
              </div>
            </div>

            <div style="display: flex; align-items: center; gap: 6px;">
              <button class="btn btn-icon" :disabled="openingPath === item.path" @click="openMedia(item.path)" title="Play media">
                <Icons name="play" :size="14" />
              </button>
              <button class="btn btn-icon" style="color: var(--error);" @click="deleteItem(item)" title="Delete">
                <Icons name="trash" :size="14" />
              </button>
            </div>
          </div>
        </div>

        <div v-else class="md3-card" style="text-align: center; padding: 24px 16px; opacity: 0.6;">
          <Icons name="folder" :size="28" style="color: var(--on-surface-variant); margin-bottom: 8px;" />
          <div style="font-size: 12px; color: var(--on-surface-variant);">No downloaded files yet</div>
        </div>
      </div>

            <div v-show="activeTab === 'cookies'">
        
                <section class="md3-card" style="margin-top: 4px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div class="icon-badge" :class="cookiesActive ? '' : 'secondary'">
                <Icons name="settings" :size="16" />
              </div>
              <div>
                <div style="font-size: 13px; font-weight: 600; color: var(--on-surface);">Platform cookies</div>
                <div style="font-size: 11px; color: var(--on-surface-variant);">
                  {{ cookiesActive ? `${cookiesLines} lines configured` : 'No cookies configured' }}
                </div>
              </div>
            </div>
            <span class="badge-pill" :class="{ active: cookiesActive }">
              {{ cookiesActive ? 'Active' : 'Not set' }}
            </span>
          </div>

                    <div style="margin-top: 10px;">
            <textarea
              class="cookies-textarea"
              v-model="cookiesText"
              placeholder="# Paste Netscape cookies.txt or standard header string here&#10;.tiktok.com&#9;TRUE&#9;/&#9;TRUE&#9;0&#9;sessionid&#9;...&#10;.instagram.com&#9;TRUE&#9;/&#9;TRUE&#9;0&#9;sessionid&#9;..."
            ></textarea>
          </div>

                    <div style="display: flex; gap: 8px; margin-top: 12px;">
            <button class="btn btn-primary" style="flex: 1; padding: 10px;" @click="saveCookies">
              <Icons name="check" :size="14" />
              Save cookies
            </button>
            <button
              v-if="cookiesActive"
              class="btn btn-secondary"
              style="padding: 10px 14px; color: var(--error);"
              @click="clearCookies"
            >
              <Icons name="trash" :size="14" />
              Clear
            </button>
          </div>
        </section>

                <div class="section-title">Cookie guide</div>
        
        <div class="md3-card">
          <div style="font-size: 13px; font-weight: 600; color: var(--on-surface); margin-bottom: 6px;">
            Why configure cookies?
          </div>
          <div style="font-size: 12px; color: var(--on-surface-variant); line-height: 1.6;">
            Platforms often restrict or rate-limit anonymous requests. Adding your browser cookies allows HyperDL to authenticate queries as your account session, enabling:
          </div>
          <ul style="margin: 8px 0 0 16px; font-size: 12px; color: var(--on-surface-variant); line-height: 1.6;">
            <li>Full 1080p and original stream bitrates without watermarks</li>
            <li>Private reels, friend-only TikToks, and restricted posts</li>
            <li>Higher rate limits and automated challenge bypassing</li>
          </ul>
        </div>

        <div class="md3-card">
          <div style="font-size: 13px; font-weight: 600; color: var(--on-surface); margin-bottom: 8px;">
            How to export cookies
          </div>
          <div class="guide-steps">
            <div class="guide-step">
              <div class="step-num">1</div>
              <div class="step-desc">
                Install a browser extension such as <b>Get cookies.txt LOCALLY</b> on Kiwi Browser, Firefox Android, or desktop Chrome.
              </div>
            </div>
            <div class="guide-step">
              <div class="step-num">2</div>
              <div class="step-desc">
                Sign in to TikTok, Instagram, or X in that browser.
              </div>
            </div>
            <div class="guide-step">
              <div class="step-num">3</div>
              <div class="step-desc">
                Open the extension, export your cookies, and copy the text.
              </div>
            </div>
            <div class="guide-step">
              <div class="step-num">4</div>
              <div class="step-desc">
                Paste the text into the box above and tap <b>Save cookies</b>. The file is saved at <code style="font-size: 11px; background: var(--surface-container-high); padding: 1px 4px; border-radius: 4px;">/data/adb/hyperdl/cookies.txt</code> with secure root permissions (0600).
              </div>
            </div>
          </div>
        </div>

      </div>

            <div v-show="activeTab === 'console'">
        
                <section class="md3-card" style="margin-top: 4px;">
          <div style="font-size: 13px; font-weight: 600; color: var(--on-surface); margin-bottom: 12px;">
            System environment
          </div>

          <div style="display: flex; flex-direction: column; gap: 8px; font-size: 12px;">
            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--surface-container-high); padding-bottom: 6px;">
              <span style="color: var(--on-surface-variant);">Python runtime</span>
              <span style="font-family: var(--font-mono); color: var(--on-surface);">{{ sysInfo.python || 'Auto-detecting...' }}</span>
            </div>
            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--surface-container-high); padding-bottom: 6px;">
              <span style="color: var(--on-surface-variant);">Available storage</span>
              <span style="font-family: var(--font-mono); color: var(--on-surface);">{{ sysInfo.storage_free || storageFree || '—' }}</span>
            </div>
            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--surface-container-high); padding-bottom: 6px;">
              <span style="color: var(--on-surface-variant);">Stored cookies</span>
              <span style="color: var(--on-surface);">{{ cookiesActive ? 'Active' : 'Not set' }}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--on-surface-variant);">Root bridge</span>
              <span style="color: var(--on-surface);">KernelSU / APatch</span>
            </div>
          </div>
        </section>

                <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 18px; margin-bottom: 8px;">
          <div class="section-title" style="margin: 0;">Engine log</div>
          <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px; gap: 4px;" @click="fetchLogs">
            <Icons name="refresh" :size="12" />
            Refresh
          </button>
        </div>

        <div class="terminal-card">
          <pre class="terminal-text">{{ logContent }}</pre>
        </div>

      </div>

            <div style="text-align: center; font-size: 11px; opacity: 0.45; padding: 24px 0 12px 0;">
        HyperDL · by @itswill00
      </div>

    </main>

        <transition name="toast-fade">
      <div v-if="toastMsg" class="toast-pill">
        <Icons name="check" :size="14" style="color: var(--primary);" />
        <span>{{ toastMsg }}</span>
      </div>
    </transition>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { execCommand, openMediaFile, openFolder, base64EncodeUtf8, base64DecodeUtf8 } from '@/helpers/shell.js'
import Icons from '@/components/Icons.vue'

const activeTab = ref('download')
const url = ref('')
const selectedFormat = ref('video')
const isProcessing = ref(false)
const autoDl = ref(false)
const storageFree = ref('')
const toastMsg = ref('')

const cookiesText = ref('')
const cookiesActive = ref(false)
const cookiesLines = ref(0)

const sysInfo = ref({ python: '', storage_free: '' })
const logContent = ref('Loading console log...')

let toastTimer = null
let pollTimer = null

const task = ref({
  status: 'idle',
  percent: 0,
  speed: '',
  downloaded: '',
  total: '',
  title: '',
  file_path: '',
  error: ''
})

const historyList = ref([])

function showToast(msg) {
  toastMsg.value = msg
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastMsg.value = '' }, 2500)
}

const supportedPlatforms = [
  { id: 'tiktok', name: 'TikTok' },
  { id: 'instagram', name: 'Instagram' },
  { id: 'x', name: 'X' },
  { id: 'youtube', name: 'YouTube' },
  { id: 'facebook', name: 'Facebook' },
  { id: 'reddit', name: 'Reddit' },
  { id: 'pinterest', name: 'Pinterest' }
]

const detectedPlatform = computed(() => {
  const u = url.value.toLowerCase()
  if (u.includes('tiktok.com')) return { name: 'TikTok', id: 'tiktok' }
  if (u.includes('instagram.com') || u.includes('instagr.am')) return { name: 'Instagram', id: 'instagram' }
  if (u.includes('twitter.com') || u.includes('x.com') || u.includes('t.co')) return { name: 'X', id: 'x' }
  if (u.includes('youtube.com') || u.includes('youtu.be')) return { name: 'YouTube', id: 'youtube' }
  if (u.includes('facebook.com') || u.includes('fb.watch')) return { name: 'Facebook', id: 'facebook' }
  if (u.includes('reddit.com')) return { name: 'Reddit', id: 'reddit' }
  if (u.includes('pinterest.com')) return { name: 'Pinterest', id: 'pinterest' }
  return { name: 'Direct link', id: 'link' }
})

const taskStatusTitle = computed(() => {
  switch (task.value.status) {
    case 'resolving': return 'Connecting...'
    case 'downloading': return 'Downloading...'
    case 'completed': return 'Download complete'
    case 'error': return 'Download failed'
    default: return 'Ready'
  }
})

function getExtIcon(ext) {
  const e = (ext || '').toLowerCase()
  if (['mp4', 'mkv', 'webm', 'mov'].includes(e)) return 'video'
  if (['mp3', 'm4a', 'aac', 'ogg'].includes(e)) return 'music'
  return 'image'
}

async function runBridge(action, ...args) {
  const params = args.map(a => `"${String(a).replace(/"/g, '\\"')}"`).join(' ')
  
  const cmd = `sh -c '
    if [ -x /data/adb/modules/hyperdl/system/bin/libhyperdl.so ]; then
      /data/adb/modules/hyperdl/system/bin/libhyperdl.so ${action} ${params}
    elif [ -x /data/data/com.termux/files/home/HyperDL_Module/system/bin/libhyperdl.so ]; then
      /data/data/com.termux/files/home/HyperDL_Module/system/bin/libhyperdl.so ${action} ${params}
    else
      echo "binary_not_found"
    fi
  '`
  
  const res = await execCommand(cmd, 15000)
  return (res || '').trim()
}

async function pasteClipboard() {
  try {
    if (navigator.clipboard && navigator.clipboard.readText) {
      const text = await navigator.clipboard.readText()
      if (text) {
        url.value = text.trim()
        showToast('Link pasted')
        return
      }
    }
  } catch (e) {}

  try {
    const text = await execCommand('cmd clipboard get 2>/dev/null || termux-clipboard-get 2>/dev/null')
    if (text && text.trim()) {
      url.value = text.trim()
      showToast('Link pasted')
    } else {
      showToast('Clipboard is empty')
    }
  } catch (e) {
    showToast('Unable to read clipboard')
  }
}

async function startDownload() {
  if (!url.value.trim() || isProcessing.value) return
  isProcessing.value = true
  task.value = {
    status: 'resolving',
    percent: 5,
    speed: '',
    downloaded: '',
    total: '',
    title: url.value,
    file_path: '',
    error: ''
  }

  showToast('Starting download...')
  try {
    await runBridge('download', url.value.trim(), selectedFormat.value)
    startPolling()
  } catch (e) {
    task.value.status = 'error'
    task.value.error = String(e)
    isProcessing.value = false
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const raw = await runBridge('status')
      if (!raw || raw === 'bridge_not_found') return
      
      const parsed = JSON.parse(raw)
      task.value = { ...task.value, ...parsed }

      if (parsed.status === 'completed') {
        clearInterval(pollTimer)
        pollTimer = null
        isProcessing.value = false
        showToast('Download complete')
        fetchHistory()
        fetchLogs()
      } else if (parsed.status === 'error') {
        clearInterval(pollTimer)
        pollTimer = null
        isProcessing.value = false
        showToast('Download failed')
        fetchLogs()
      }
    } catch (e) {}
  }, 400)
}

async function fetchHistory() {
  try {
    const raw = await runBridge('list')
    if (raw && raw.startsWith('[')) {
      historyList.value = JSON.parse(raw)
    }
  } catch (e) {}
}

async function deleteItem(item) {
  if (!confirm(`Delete ${item.name}?`)) return
  try {
    await runBridge('delete', item.path)
    showToast('File deleted')
    fetchHistory()
  } catch (e) {
    showToast('Failed to delete file')
  }
}

const openingPath = ref(null)
const openingFolder = ref(false)

async function openMedia(filePath) {
  if (!filePath || openingPath.value) return
  openingPath.value = filePath
  showToast('Opening media...')
  try {
    await openMediaFile(filePath)
  } catch (e) {
    showToast('Failed to open media')
  } finally {
    openingPath.value = null
  }
}

async function openMediaFolder() {
  if (openingFolder.value) return
  openingFolder.value = true
  showToast('Opening folder...')
  try {
    await openFolder()
  } catch (e) {
    showToast('Failed to open folder')
  } finally {
    openingFolder.value = false
  }
}

async function toggleAutoDl() {
  const nextState = !autoDl.value
  try {
    await runBridge('toggle_autodl', nextState ? '1' : '0')
    autoDl.value = nextState
    showToast(nextState ? 'Clipboard monitor enabled' : 'Clipboard monitor disabled')
  } catch (e) {
    showToast('Failed to update setting')
  }
}

async function loadCookies() {
  try {
    const raw = await runBridge('get_cookies')
    if (raw && raw.startsWith('{')) {
      const res = JSON.parse(raw)
      cookiesActive.value = !!res.exists
      cookiesLines.value = res.lines || 0
      if (res.content_b64) {
        cookiesText.value = base64DecodeUtf8(res.content_b64)
      }
    }
  } catch (e) {}
}

async function saveCookies() {
  try {
    const b64 = base64EncodeUtf8(cookiesText.value.trim())
    const raw = await runBridge('save_cookies', b64)
    if (raw && raw.startsWith('{')) {
      const res = JSON.parse(raw)
      cookiesActive.value = (res.lines > 0)
      cookiesLines.value = res.lines || 0
      showToast('Cookies saved')
    }
  } catch (e) {
    showToast('Failed to save cookies')
  }
}

async function clearCookies() {
  if (!confirm('Clear all stored cookies?')) return
  try {
    await runBridge('clear_cookies')
    cookiesText.value = ''
    cookiesActive.value = false
    cookiesLines.value = 0
    showToast('Cookies cleared')
  } catch (e) {
    showToast('Failed to clear cookies')
  }
}

async function fetchLogs() {
  try {
    const logs = await runBridge('get_logs')
    logContent.value = logs || 'No log entries.'
  } catch (e) {
    logContent.value = 'Failed to load console logs.'
  }
}

async function loadSystemInfo() {
  try {
    const raw = await runBridge('info')
    if (raw && raw.startsWith('{')) {
      const info = JSON.parse(raw)
      storageFree.value = info.storage_free || ''
      sysInfo.value = info
      cookiesActive.value = !!info.has_cookies
    }
    
    const autoRaw = await runBridge('get_autodl')
    if (autoRaw && autoRaw.startsWith('{')) {
      const autoInfo = JSON.parse(autoRaw)
      autoDl.value = !!autoInfo.autodl
    }
  } catch (e) {}
}

onMounted(() => {
  loadSystemInfo()
  fetchHistory()
  loadCookies()
  fetchLogs()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (toastTimer) clearTimeout(toastTimer)
})
</script>

<style scoped>
.tabs-control {
  display: flex;
  background: var(--surface-container-low);
  border: 1px solid var(--surface-container-high);
  border-radius: 14px;
  padding: 3px;
  gap: 4px;
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: var(--on-surface-variant);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn.active {
  background: var(--surface-container-high);
  color: var(--on-surface);
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
}

.cookies-textarea {
  width: 100%;
  height: 140px;
  background: var(--surface-container-low);
  border: 1px solid var(--outline-variant);
  border-radius: 12px;
  color: var(--on-surface);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.4;
  padding: 10px;
  resize: vertical;
  outline: none;
}

.cookies-textarea:focus {
  border-color: var(--primary);
}

.guide-steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 6px;
}

.guide-step {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.step-num {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  color: var(--on-surface);
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}

.step-desc {
  font-size: 12px;
  color: var(--on-surface-variant);
  line-height: 1.5;
}

.terminal-card {
  background: var(--surface-container-lowest);
  border: 1px solid var(--surface-container-high);
  border-radius: 12px;
  padding: 12px;
  max-height: 260px;
  overflow-y: auto;
}

.terminal-text {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--on-surface-variant);
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  line-height: 1.4;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.toast-fade-enter-from {
  opacity: 0;
  transform: translate(-50%, 15px);
}

.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -10px);
}
</style>
