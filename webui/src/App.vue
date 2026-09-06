<template>
  <div class="app-shell">
    
    <!-- Top Header -->
    <header class="page-header">
      <div>
        <div class="page-header-title">HyperDL</div>
        <div class="page-header-sub">Media Downloader</div>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <span class="badge-pill" v-if="storageFree">
          {{ storageFree }} Free
        </span>
        <span class="badge-pill active">
          v1.0.0
        </span>
      </div>
    </header>

    <!-- Main Content Area -->
    <main class="content-area">

      <!-- Media Input Card -->
      <section class="md3-card" style="margin-top: 2px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
          <span style="font-size: 13px; font-weight: 600; color: var(--on-surface);">New Download</span>
          <span class="badge-pill" :class="{ active: detectedPlatform.name !== 'Unknown' }" style="font-size: 10px;">
            {{ detectedPlatform.name }}
          </span>
        </div>

        <!-- URL Input Field with Clear & Paste -->
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

        <!-- Format Options -->
        <div style="margin-top: 14px;">
          <div style="font-size: 11px; color: var(--on-surface-variant); margin-bottom: 6px; font-weight: 500;">
            FORMAT
          </div>
          <div class="chips-row">
            <div
              class="chip-item"
              :class="{ active: selectedFormat === 'video' }"
              @click="selectedFormat = 'video'"
            >
              <Icons name="video" :size="14" />
              <span>Video (HD)</span>
            </div>
            <div
              class="chip-item"
              :class="{ active: selectedFormat === 'audio' }"
              @click="selectedFormat = 'audio'"
            >
              <Icons name="music" :size="14" />
              <span>Audio (MP3)</span>
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

        <!-- Download Action Button -->
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

      <!-- Active Progress Card -->
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

        <!-- Progress Bar -->
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: task.percent + '%' }"></div>
        </div>

        <!-- Progress Metrics -->
        <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--on-surface-variant); margin-top: 8px; font-family: var(--font-mono);">
          <span>{{ task.downloaded ? `${task.downloaded} / ${task.total}` : (task.status === 'resolving' ? 'Connecting to source...' : '') }}</span>
          <span>{{ task.speed ? task.speed : '' }}</span>
        </div>

        <!-- Error Message -->
        <div v-if="task.status === 'error'" style="margin-top: 10px; color: var(--error); font-size: 12px; background: var(--error-container); padding: 8px 12px; border-radius: 8px;">
          {{ task.error || 'Failed to complete download' }}
        </div>

        <!-- Completion Actions -->
        <div v-if="task.status === 'completed'" style="display: flex; gap: 8px; margin-top: 12px;">
          <button class="btn btn-primary" style="flex: 1; padding: 8px 12px; font-size: 12px;" @click="openMedia(task.file_path)">
            <Icons name="play" :size="14" />
            Open Media
          </button>
          <button class="btn btn-secondary" style="padding: 8px 12px; font-size: 12px;" @click="openMediaFolder">
            <Icons name="folder" :size="14" />
            Show in Folder
          </button>
        </div>
      </section>

      <!-- Automation Section -->
      <div class="section-title">Automation</div>
      <div class="md3-list-group">
        <div class="md3-list-row">
          <div style="display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1;">
            <div class="icon-badge secondary">
              <Icons name="clipboard" :size="18" />
            </div>
            <div>
              <div style="font-size: 13px; font-weight: 600; color: var(--on-surface);">Clipboard Monitoring</div>
              <div style="font-size: 11px; color: var(--on-surface-variant);">Automatically download supported links when copied</div>
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
              <div style="font-size: 13px; font-weight: 600; color: var(--on-surface);">Destination Folder</div>
              <div style="font-size: 11px; color: var(--on-surface-variant); font-family: var(--font-mono);">/Download/HyperDL</div>
            </div>
          </div>
          <Icons name="chevron-right" :size="16" style="color: var(--on-surface-variant);" />
        </div>
      </div>

      <!-- Recent Downloads -->
      <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 18px; margin-bottom: 8px;">
        <div class="section-title" style="margin: 0;">Recent Downloads ({{ historyList.length }})</div>
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
                {{ item.size }} · {{ item.ext.toUpperCase() }}
              </div>
            </div>
          </div>

          <div style="display: flex; align-items: center; gap: 6px;">
            <button class="btn btn-icon" @click="openMedia(item.path)" title="Play Media">
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

      <!-- Clean Minimal Footer -->
      <div style="text-align: center; font-size: 11px; opacity: 0.45; padding: 24px 0 12px 0;">
        HyperDL · Crafted by @itswill00
      </div>

    </main>

    <!-- Toast Notification -->
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
import { execCommand, openMediaFile, openFolder } from '@/helpers/shell.js'
import Icons from '@/components/Icons.vue'

const url = ref('')
const selectedFormat = ref('video')
const isProcessing = ref(false)
const autoDl = ref(false)
const storageFree = ref('')
const toastMsg = ref('')
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

/* Platform detection */
const detectedPlatform = computed(() => {
  const u = url.value.toLowerCase()
  if (u.includes('tiktok.com')) return { name: 'TikTok' }
  if (u.includes('instagram.com') || u.includes('instagr.am')) return { name: 'Instagram' }
  if (u.includes('twitter.com') || u.includes('x.com') || u.includes('t.co')) return { name: 'X' }
  if (u.includes('youtube.com') || u.includes('youtu.be')) return { name: 'YouTube' }
  if (u.includes('facebook.com') || u.includes('fb.watch')) return { name: 'Facebook' }
  if (u.includes('reddit.com')) return { name: 'Reddit' }
  if (u.includes('pinterest.com')) return { name: 'Pinterest' }
  return { name: 'Supported' }
})

const taskStatusTitle = computed(() => {
  switch (task.value.status) {
    case 'resolving': return 'Connecting...'
    case 'downloading': return 'Downloading...'
    case 'completed': return 'Download Complete'
    case 'error': return 'Download Failed'
    default: return 'Active Download'
  }
})

function getExtIcon(ext) {
  const e = (ext || '').toLowerCase()
  if (['mp4', 'mkv', 'webm', 'mov'].includes(e)) return 'video'
  if (['mp3', 'm4a', 'aac', 'ogg'].includes(e)) return 'music'
  return 'image'
}

/* Bridge Execution Runner */
async function runBridge(action, ...args) {
  const params = args.map(a => `"${String(a).replace(/"/g, '\\"')}"`).join(' ')
  
  const cmd = `sh -c '
    if [ -f /data/adb/modules/hyperdl/engine/bridge.sh ]; then
      sh /data/adb/modules/hyperdl/engine/bridge.sh ${action} ${params}
    elif [ -f /data/data/com.termux/files/home/HyperDL_Module/engine/bridge.sh ]; then
      sh /data/data/com.termux/files/home/HyperDL_Module/engine/bridge.sh ${action} ${params}
    else
      echo "bridge_not_found"
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
        showToast('Download finished')
        fetchHistory()
      } else if (parsed.status === 'error') {
        clearInterval(pollTimer)
        pollTimer = null
        isProcessing.value = false
        showToast('Download failed')
      }
    } catch (e) {
      // Ignore poll error
    }
  }, 1000)
}

async function fetchHistory() {
  try {
    const raw = await runBridge('list')
    if (raw && raw.startsWith('[')) {
      historyList.value = JSON.parse(raw)
    }
  } catch (e) {
    console.error('Failed to list history:', e)
  }
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

function openMedia(filePath) {
  if (!filePath) return
  openMediaFile(filePath)
}

function openMediaFolder() {
  openFolder()
}

async function toggleAutoDl() {
  const nextState = !autoDl.value
  try {
    await runBridge('toggle_autodl', nextState ? '1' : '0')
    autoDl.value = nextState
    showToast(nextState ? 'Clipboard monitoring enabled' : 'Clipboard monitoring disabled')
  } catch (e) {
    showToast('Failed to update setting')
  }
}

async function loadSystemInfo() {
  try {
    const raw = await runBridge('info')
    if (raw && raw.startsWith('{')) {
      const info = JSON.parse(raw)
      storageFree.value = info.storage_free || ''
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
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (toastTimer) clearTimeout(toastTimer)
})
</script>

<style scoped>
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
