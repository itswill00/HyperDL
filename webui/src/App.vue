<template>
  <div class="app-shell">
    
        <header class="page-header">
      <div>
        <div class="page-header-title">HyperDL</div>
        <div class="page-header-sub">Media downloader</div>
      </div>
      <div style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">
        <span class="badge-pill offline" v-if="!isOnline">
          <Icons name="wifi-off" :size="11" />
          Offline
        </span>
        <span class="badge-pill active" v-else @click="onVersionClick" style="cursor: pointer; user-select: none;">
          {{ sysInfo.version || 'v1.3.18' }}
          <Icons v-if="isVaultActive" name="lock" :size="11" style="margin-left: 4px; color: #a1a1aa;" />
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
        <button
          v-if="isVaultActive"
          class="tab-btn"
          :class="{ active: activeTab === 'vault' }"
          @click="activeTab = 'vault'; fetchVaultHistory()"
        >
          <Icons name="lock" :size="14" />
          <span>Vault</span>
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

          <div v-if="!isOnline" class="offline-notice-box">
            <Icons name="wifi-off" :size="14" style="color: var(--error); flex-shrink: 0;" />
            <div style="flex: 1;">
              <strong style="color: var(--on-surface);">No internet connection:</strong>
              Connect to Wi-Fi or mobile data to start downloads.
            </div>
          </div>

                    <div class="text-input-wrapper">
            <input
              ref="urlInput"
              type="url"
              class="text-input"
              v-model="url"
              placeholder="Paste media link here..."
              enterkeyhint="go"
              @input="onUrlInput"
              @paste="onPasteInput"
              @keydown.enter.prevent="startDownload"
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
              v-else
              class="btn btn-secondary"
              style="padding: 6px 12px; font-size: 11px; margin-left: 4px;"
              @click="pasteClipboard"
            >
              <Icons name="clipboard" :size="13" />
              Paste
            </button>
          </div>

          <!-- Smart Clipboard Sniffer Banner -->
          <div v-if="detectedClipUrl" class="clip-sniffer-banner">
            <div class="clip-sniffer-icon">
              <Icons name="clipboard" :size="15" />
            </div>
            <div class="clip-sniffer-content">
              <div class="clip-sniffer-title">Media link detected</div>
              <div class="clip-sniffer-url">{{ formatTruncatedUrl(detectedClipUrl) }}</div>
            </div>
            <div class="clip-sniffer-actions">
              <button class="btn btn-primary clip-action-btn" @click="applyClipUrl(true)">
                <Icons name="download" :size="11" />
                <span>Go</span>
              </button>
              <button class="btn btn-secondary clip-action-btn" @click="applyClipUrl(false)">
                <span>Paste</span>
              </button>
              <button class="btn btn-icon clip-dismiss-btn" @click="dismissClipUrl" title="Dismiss">
                <Icons name="close" :size="13" />
              </button>
            </div>
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

          <div v-if="detectedPlatform.id === 'instagram'" class="platform-notice-box">
            <Icons name="info" :size="14" style="color: var(--secondary); margin-top: 1px;" />
            <div style="flex: 1;">
              <span style="font-weight: 600; color: var(--on-surface);">Meta Anti-Bot:</span>
              Instagram frequently blocks anonymous access. If download fails, add your session cookies in the
              <a href="javascript:void(0)" @click="activeTab = 'cookies'" style="color: var(--primary); text-decoration: underline; font-weight: 600;">Cookies tab</a>.
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
                <span>Audio (FLAC)</span>
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
            <div class="format-desc-hint">
              <span v-if="selectedFormat === 'video'">Original video stream with best available audio</span>
              <span v-else-if="selectedFormat === 'audio'">Lossless studio audio (FLAC 24-bit / 48 kHz HD)</span>
              <span v-else-if="selectedFormat === 'album'">Original high-res photos & carousel images</span>
            </div>
          </div>

                    <div style="margin-top: 16px;">
            <button
              class="btn btn-primary"
              :class="{ 'btn-offline': !isOnline }"
              style="width: 100%; height: 44px; font-size: 14px;"
              :disabled="!url.trim() || isProcessing"
              @click="startDownload"
            >
              <Icons :name="!isOnline ? 'wifi-off' : isProcessing ? 'refresh' : 'download'" :size="16" />
              <span>{{ !isOnline ? 'Download (Offline)' : isProcessing ? 'Downloading...' : 'Download' }}</span>
            </button>
          </div>
        </section>

                <section v-if="task.status !== 'idle'" class="md3-card" :style="{ borderColor: task.status === 'paused' ? 'var(--secondary)' : 'var(--primary)' }">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1;">
              <div class="icon-badge" :class="{ secondary: task.status === 'paused' }">
                <Icons :name="task.status === 'completed' ? 'check' : (task.status === 'paused' ? 'pause' : 'download')" :size="18" />
              </div>
              <div style="min-width: 0; flex: 1;">
                <div style="font-size: 13px; font-weight: 600; color: var(--on-surface);">
                  {{ taskStatusTitle }}
                </div>
                <div style="font-size: 11px; color: var(--on-surface-variant); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                  {{ task.title || task.url || url }}
                </div>
              </div>
            </div>
            <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
              <span class="badge-pill" :class="{ active: task.status === 'completed', paused: task.status === 'paused' }">
                {{ task.status === 'paused' ? 'Paused' : `${task.percent}%` }}
              </span>

              <!-- Downloading / Resolving controls -->
              <template v-if="task.status === 'resolving' || task.status === 'downloading'">
                <button
                  class="btn btn-secondary"
                  style="padding: 3px 8px; font-size: 11px; height: 26px; gap: 4px;"
                  @click="pauseDownload()"
                  title="Pause download"
                >
                  <Icons name="pause" :size="11" />
                  <span>Pause</span>
                </button>
                <button
                  class="btn btn-secondary"
                  style="padding: 3px 8px; font-size: 11px; color: var(--error); border-color: rgba(255, 107, 107, 0.3); height: 26px; gap: 4px;"
                  @click="cancelDownload"
                  title="Cancel download"
                >
                  <Icons name="close" :size="11" />
                  <span>Cancel</span>
                </button>
              </template>

              <!-- Paused controls -->
              <template v-else-if="task.status === 'paused'">
                <button
                  class="btn btn-primary"
                  style="padding: 3px 10px; font-size: 11px; height: 26px; gap: 4px;"
                  @click="resumeDownload"
                  title="Resume download"
                >
                  <Icons name="play" :size="11" />
                  <span>Resume</span>
                </button>
                <button
                  class="btn btn-secondary"
                  style="padding: 3px 8px; font-size: 11px; color: var(--error); border-color: rgba(255, 107, 107, 0.3); height: 26px; gap: 4px;"
                  @click="cancelDownload"
                  title="Cancel download"
                >
                  <Icons name="close" :size="11" />
                  <span>Cancel</span>
                </button>
              </template>

              <!-- Completed or Error dismiss -->
              <button
                v-else-if="task.status === 'completed' || task.status === 'error'"
                class="icon-btn"
                style="width: 26px; height: 26px; font-size: 11px;"
                @click="dismissTask"
                title="Dismiss"
              >
                ✕
              </button>
            </div>
          </div>

          <div class="progress-track">
            <div
              class="progress-fill"
              :class="{ indeterminate: task.status === 'resolving', paused: task.status === 'paused' }"
              :style="{ width: (task.status === 'resolving' ? 100 : task.percent) + '%' }"
            ></div>
          </div>

          <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--on-surface-variant); margin-top: 8px; font-family: inherit; font-variant-numeric: tabular-nums;">
            <span>{{ formatProgressInfo(task) }}</span>
            <span>{{ formatSpeedInfo(task) }}</span>
          </div>

          <!-- Paused banner with instant resume -->
          <div v-if="task.status === 'paused'" style="margin-top: 10px; font-size: 12px; background: rgba(255, 183, 77, 0.12); border: 1px solid rgba(255, 183, 77, 0.3); padding: 9px 12px; border-radius: 8px; color: #ffb74d;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
              <div style="display: flex; align-items: center; gap: 6px; min-width: 0; flex: 1;">
                <Icons name="pause" :size="13" />
                <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                  {{ task.error || 'Download paused. Existing progress is preserved.' }}
                </span>
              </div>
              <button
                class="btn btn-primary"
                style="padding: 4px 12px; font-size: 11px; height: 26px; gap: 4px; flex-shrink: 0;"
                @click="resumeDownload"
              >
                <Icons name="play" :size="11" />
                <span>Resume</span>
              </button>
            </div>
          </div>

          <!-- Error details -->
          <div v-if="task.status === 'error'" style="margin-top: 10px; color: var(--error); font-size: 12px; background: var(--error-container); padding: 10px 12px; border-radius: 8px;">
            <div style="display: flex; align-items: flex-start; gap: 8px;">
              <Icons :name="isNetworkError(task.error) ? 'wifi-off' : 'info'" :size="15" style="color: var(--error); flex-shrink: 0; margin-top: 1px;" />
              <div style="font-weight: 500; word-break: break-word; flex: 1;">{{ formatErrorMessage(task.error) }}</div>
            </div>
            <div style="display: flex; gap: 8px; margin-top: 10px;">
              <button
                class="btn btn-primary"
                style="flex: 1; font-size: 11px; padding: 6px 10px; gap: 4px;"
                @click="resumeDownload"
              >
                <Icons name="play" :size="12" />
                Resume
              </button>
              <button
                v-if="isNetworkError(task.error)"
                class="btn btn-secondary"
                style="flex: 1; font-size: 11px; padding: 6px 10px; border-color: rgba(255,255,255,0.15);"
                @click="testConnectivity"
              >
                Check Connection
              </button>
              <button
                v-else-if="(task.error || '').toLowerCase().includes('cookie') || (task.error || '').toLowerCase().includes('instagram')"
                class="btn btn-secondary"
                style="flex: 1; font-size: 11px; padding: 6px 10px; border-color: rgba(255,255,255,0.15);"
                @click="activeTab = 'cookies'"
              >
                Configure Cookies
              </button>
              <button
                class="btn btn-secondary"
                style="padding: 6px 10px; font-size: 11px; color: var(--error); border-color: rgba(255, 107, 107, 0.3);"
                @click="cancelDownload"
                title="Discard task"
              >
                <Icons name="close" :size="12" />
              </button>
            </div>
          </div>

                    <div v-if="task.status === 'completed'" style="display: flex; gap: 8px; margin-top: 12px;">
            <button class="btn btn-primary" :disabled="openingPath === task.file_path" style="flex: 1; padding: 8px 12px; font-size: 12px;" @click="openMedia(task.file_path)">
              <Icons name="play" :size="14" />
              {{ openingPath === task.file_path ? 'Opening...' : 'Open media' }}
            </button>
            <button class="btn btn-secondary" :disabled="openingFolder" style="padding: 8px 14px; font-size: 12px;" @click="openMediaFolder">
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
                <div style="font-size: 11px; color: var(--on-surface-variant); font-family: inherit;">/Download/HyperDL</div>
              </div>
            </div>
            <Icons name="chevron-right" :size="16" style="color: var(--on-surface-variant);" />
          </div>
        </div>

        <!-- Storage Breakdown & Quick Cleaner Card -->
        <div class="storage-card" v-if="storageStats.free_size || storageStats.media_count > 0">
          <div class="storage-header">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div class="icon-badge secondary" style="width: 28px; height: 28px;">
                <Icons name="hard-drive" :size="15" />
              </div>
              <div>
                <div style="font-size: 12px; font-weight: 600; color: var(--on-surface);">Storage & Cache</div>
                <div style="font-size: 11px; color: var(--on-surface-variant);">
                  {{ storageStats.media_count }} file{{ storageStats.media_count === 1 ? '' : 's' }} ({{ storageStats.media_size }}) · {{ storageStats.free_size }} free
                </div>
              </div>
            </div>
            <div>
              <button
                v-if="storageStats.junk_count > 0"
                class="btn btn-secondary junk-clean-btn active"
                :disabled="isCleaningJunk"
                @click="cleanJunk"
                title="Clean leftover temporary files"
              >
                <Icons name="broom" :size="12" />
                <span>Clean {{ storageStats.junk_size }}</span>
              </button>
              <button
                v-else
                class="btn btn-secondary junk-clean-btn"
                :disabled="isCleaningJunk"
                @click="fetchStorageStats"
                title="Refresh storage"
              >
                <Icons name="refresh" :size="12" />
                <span>Optimal</span>
              </button>
            </div>
          </div>

          <div class="storage-bar-track" v-if="storageBarPercent > 0">
            <div class="storage-bar-fill media" :style="{ width: storageBarPercent + '%' }"></div>
          </div>
        </div>

        <!-- Recent downloads header / contextual selection toolbar -->
        <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 18px; margin-bottom: 8px; min-height: 32px;">
          <!-- Selection Mode active: Contextual Action Bar -->
          <template v-if="selectedFiles.size > 0">
            <div style="display: flex; align-items: center; gap: 8px;">
              <button class="icon-btn" style="width: 28px; height: 28px;" @click="clearSelection" title="Cancel selection">
                <Icons name="close" :size="15" />
              </button>
              <span style="font-size: 13px; font-weight: 600; color: var(--on-surface);">
                {{ selectedFiles.size }} selected
              </span>
            </div>
            <div style="display: flex; gap: 6px; align-items: center;">
              <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;" @click="toggleSelectAll">
                {{ isAllSelected ? 'Deselect all' : 'Select all' }}
              </button>
              <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px; color: var(--error); border-color: rgba(229, 153, 149, 0.35); background: rgba(229, 153, 149, 0.1); gap: 4px;" @click="deleteSelected">
                <Icons name="trash" :size="12" />
                <span>Delete</span>
              </button>
            </div>
          </template>

          <!-- Normal Mode: Section Title & Actions -->
          <template v-else>
            <div class="section-title" style="margin: 0;">Recent downloads ({{ historyList.length }})</div>
            <div style="display: flex; gap: 6px; align-items: center;" v-if="historyList.length > 0">
              <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;" @click="toggleSelectAll">
                Select
              </button>
              <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px; gap: 4px;" @click="fetchHistory" title="Refresh list">
                <Icons name="refresh" :size="12" />
              </button>
            </div>
          </template>
        </div>

        <!-- Search and Category Filters -->
        <div class="recent-controls-card" v-if="historyList.length > 0">
          <div class="search-input-box">
            <Icons name="search" :size="14" style="color: var(--on-surface-variant); flex-shrink: 0;" />
            <input
              type="text"
              class="search-input"
              v-model="searchQuery"
              placeholder="Search downloaded media..."
            />
            <button
              v-if="searchQuery"
              class="btn-search-clear"
              @click="searchQuery = ''"
              title="Clear search"
            >
              ✕
            </button>
          </div>

          <div class="filter-chips-row">
            <button
              class="filter-chip"
              :class="{ active: selectedCategory === 'all' }"
              @click="selectedCategory = 'all'"
            >
              All ({{ historyList.length }})
            </button>
            <button
              class="filter-chip"
              :class="{ active: selectedCategory === 'video' }"
              @click="selectedCategory = 'video'"
            >
              <Icons name="video" :size="12" />
              <span>Video ({{ videoCount }})</span>
            </button>
            <button
              class="filter-chip"
              :class="{ active: selectedCategory === 'image' }"
              @click="selectedCategory = 'image'"
            >
              <Icons name="image" :size="12" />
              <span>Image ({{ imageCount }})</span>
            </button>
            <button
              class="filter-chip"
              :class="{ active: selectedCategory === 'audio' }"
              @click="selectedCategory = 'audio'"
            >
              <Icons name="music" :size="12" />
              <span>Audio ({{ audioCount }})</span>
            </button>
          </div>
        </div>

        <div class="md3-list-group" v-if="filteredHistoryList.length > 0">
          <div
            v-for="item in filteredHistoryList"
            :key="item.path"
            class="md3-list-row"
            :class="{ 'row-selected': selectedFiles.has(item.path) }"
            style="display: flex; align-items: center; gap: 10px;"
          >
            <!-- Multi-select checkbox -->
            <label class="custom-checkbox" @click.stop>
              <input
                type="checkbox"
                :checked="selectedFiles.has(item.path)"
                @change="toggleSelect(item.path)"
              />
              <span class="checkbox-box">
                <svg v-if="selectedFiles.has(item.path)" viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="3" fill="none">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </span>
            </label>

            <div style="display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; cursor: pointer;" @click="handleItemClick(item)">
              <div class="icon-badge secondary">
                <Icons :name="getExtIcon(item.ext)" :size="16" />
              </div>
              <div style="min-width: 0; flex: 1;">
                <div style="font-size: 12px; font-weight: 600; color: var(--on-surface); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                  {{ item.name }}
                </div>
                <div style="font-size: 10px; color: var(--on-surface-variant); font-family: inherit; font-variant-numeric: tabular-nums; margin-top: 2px;">
                  <span v-if="item.folder" style="color: var(--primary); font-weight: 500;">{{ item.folder }} · </span>{{ item.size }} · {{ (item.ext || '').toLowerCase() }}
                </div>
              </div>
            </div>

            <!-- Action buttons -->
            <div v-if="selectedFiles.size === 0" style="display: flex; align-items: center; gap: 6px;">
              <template v-if="isImageExt(item.ext)">
                <button class="btn btn-icon" @click.stop="openPreview(item)" title="Preview image">
                  <Icons name="eye" :size="14" />
                </button>
                <button class="btn btn-icon" :disabled="openingPath === item.path" @click.stop="openMedia(item.path)" title="Open in gallery">
                  <Icons name="external-link" :size="14" />
                </button>
              </template>
              <template v-else>
                <button class="btn btn-icon" :disabled="openingPath === item.path" @click.stop="openMedia(item.path)" :title="isVideoExt(item.ext) ? 'Play video' : (isAudioExt(item.ext) ? 'Play audio' : 'Open file')">
                  <Icons :name="isVideoExt(item.ext) || isAudioExt(item.ext) ? 'play' : 'external-link'" :size="14" />
                </button>
              </template>
              <button class="btn btn-icon" style="color: var(--error);" @click.stop="deleteItem(item)" title="Delete">
                <Icons name="trash" :size="14" />
              </button>
            </div>
          </div>
        </div>

        <div v-else-if="historyList.length > 0 && filteredHistoryList.length === 0" class="md3-card" style="text-align: center; padding: 20px 16px;">
          <div style="font-size: 12px; color: var(--on-surface-variant); margin-bottom: 8px;">
            No media matching "{{ searchQuery }}" in this filter
          </div>
          <button class="btn btn-secondary" style="padding: 6px 12px; font-size: 11px; margin: 0 auto;" @click="clearSearchAndFilter">
            Clear filter
          </button>
        </div>

        <div v-else class="md3-card" style="text-align: center; padding: 24px 16px; opacity: 0.6;">
          <Icons name="folder" :size="28" style="color: var(--on-surface-variant); margin-bottom: 8px;" />
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
            <button class="btn btn-secondary" style="padding: 10px 14px;" @click="pasteCookiesClipboard">
              <Icons name="clipboard" :size="14" />
              Paste
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

        <!-- Platform Accounts & Cookie Health Status -->
        <div class="section-title">Account sessions</div>
        <div class="md3-card" style="padding: 12px;">
          <div class="cookie-health-grid">
            <div
              v-for="acc in cookieAccounts"
              :key="acc.id"
              class="cookie-health-item"
              :class="{ active: acc.active }"
            >
              <div class="cookie-health-icon">
                <Icons :name="acc.icon" :size="15" />
              </div>
              <div class="cookie-health-info">
                <div class="cookie-health-name">{{ acc.name }}</div>
                <div class="cookie-health-desc">{{ acc.detail }}</div>
              </div>
              <span class="cookie-status-dot" :class="{ active: acc.active }" :title="acc.active ? 'Active' : 'Not configured'"></span>
            </div>
          </div>
        </div>

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
                Install a browser extension such as <b>Get cookies.txt Locally</b> on Kiwi Browser, Firefox Android, or desktop Chrome.
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
              <span style="font-family: inherit; font-variant-numeric: tabular-nums; color: var(--on-surface);">{{ sysInfo.python || 'Auto-detecting...' }}</span>
            </div>
            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--surface-container-high); padding-bottom: 6px;">
              <span style="color: var(--on-surface-variant);">Audio encoder</span>
              <span style="font-family: inherit; color: var(--on-surface);">{{ sysInfo.has_ffmpeg ? 'FFmpeg (FLAC Lossless HD)' : 'Direct Stream' }}</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--surface-container-high); padding-bottom: 6px;">
              <span style="color: var(--on-surface-variant);">yt-dlp binary</span>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-family: inherit; font-variant-numeric: tabular-nums; color: var(--on-surface);">{{ ytdlpInfo.current || '2026.08.19' }}</span>
                <button
                  class="btn"
                  :class="ytdlpInfo.has_update ? 'btn-primary' : 'btn-secondary'"
                  style="padding: 3px 8px; font-size: 10px; height: 22px; border-radius: 6px; font-weight: 600;"
                  :disabled="ytdlpChecking || ytdlpUpdating"
                  @click="handleYtdlpAction"
                >
                  <span v-if="ytdlpChecking || ytdlpUpdating" class="spin-loader" style="width: 10px; height: 10px; margin-right: 4px;">
                    <Icons name="refresh" :size="10" />
                  </span>
                  <span>{{ ytdlpButtonLabel }}</span>
                </button>
              </div>
            </div>
            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--surface-container-high); padding-bottom: 6px;">
              <span style="color: var(--on-surface-variant);">Available storage</span>
              <span style="font-family: inherit; font-variant-numeric: tabular-nums; color: var(--on-surface);">{{ sysInfo.storage_free || storageFree || '—' }}</span>
            </div>
            <div style="display: flex; justify-content: space-between; border-bottom: 1px solid var(--surface-container-high); padding-bottom: 6px;">
              <span style="color: var(--on-surface-variant);">Stored cookies</span>
              <span style="color: var(--on-surface);">{{ cookiesActive ? 'Active' : 'Not set' }}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="color: var(--on-surface-variant);">Root bridge</span>
              <span style="color: var(--on-surface);">KernelSU / APatch / Magisk</span>
            </div>
          </div>
        </section>

        <div class="section-title">Community & Support</div>
        <div class="md3-list-group">
          <a class="md3-list-row clickable" href="https://t.me/noticesa" target="_blank" rel="noopener noreferrer" style="text-decoration: none;">
            <div style="display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1;">
              <div class="icon-badge secondary">
                <Icons name="telegram" :size="18" />
              </div>
              <div>
                <div style="font-size: 13px; font-weight: 600; color: var(--on-surface);">Telegram</div>
                <div style="font-size: 11px; color: var(--on-surface-variant);">@noticesa · Updates & Discussion</div>
              </div>
            </div>
            <Icons name="chevron-right" :size="16" style="color: var(--on-surface-variant);" />
          </a>

          <a class="md3-list-row clickable" href="https://sociabuzz.com/noticesa/tribe" target="_blank" rel="noopener noreferrer" style="text-decoration: none;">
            <div style="display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1;">
              <div class="icon-badge secondary">
                <Icons name="heart" :size="18" style="color: #ff6b81;" />
              </div>
              <div>
                <div style="font-size: 13px; font-weight: 600; color: var(--on-surface);">Support Development</div>
                <div style="font-size: 11px; color: var(--on-surface-variant);">Donate via SociaBuzz Tribe</div>
              </div>
            </div>
            <Icons name="chevron-right" :size="16" style="color: var(--on-surface-variant);" />
          </a>
        </div>

                <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 18px; margin-bottom: 8px;">
          <div class="section-title" style="margin: 0;">Activity log</div>
          <div style="display: flex; gap: 6px; align-items: center;">
            <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px; gap: 4px;" @click="fetchLogs" title="Refresh log">
              <Icons name="refresh" :size="12" />
              <span>Refresh</span>
            </button>
            <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px; gap: 4px;" @click="copyLogs" title="Copy log">
              <Icons name="copy" :size="12" />
              <span>Copy</span>
            </button>
            <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px; gap: 4px; color: var(--error);" @click="clearLogs" title="Clear log">
              <Icons name="trash" :size="12" />
              <span>Clear</span>
            </button>
          </div>
        </div>

        <div class="terminal-card" ref="terminalCard">
          <pre class="terminal-text">{{ logContent }}</pre>
        </div>

      </div>

      <!-- VAULT TAB -->
      <div v-show="activeTab === 'vault' && isVaultActive">
        <section class="md3-card" style="margin-top: 4px; margin-bottom: 12px;">
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div class="icon-badge secondary">
                <Icons name="lock" :size="16" />
              </div>
              <div>
                <div style="font-size: 13px; font-weight: 600; color: var(--on-surface);">Private Vault ({{ vaultList.length }})</div>
                <div style="font-size: 11px; color: var(--on-surface-variant);">Protected with .nomedia · Hidden from gallery</div>
              </div>
            </div>
            <div style="display: flex; gap: 6px; align-items: center;">
              <button
                class="btn btn-secondary"
                style="padding: 4px 8px; font-size: 11px; display: flex; align-items: center; gap: 4px;"
                @click="isVaultBlurred = !isVaultBlurred"
              >
                <Icons :name="isVaultBlurred ? 'eye' : 'eye-off'" :size="12" />
                <span>{{ isVaultBlurred ? 'Unblur' : 'Blur' }}</span>
              </button>
              <button
                class="btn btn-secondary"
                style="padding: 4px 8px; font-size: 11px; display: flex; align-items: center; gap: 4px;"
                @click="fetchVaultHistory"
                title="Refresh vault"
              >
                <Icons name="refresh" :size="12" />
              </button>
            </div>
          </div>
        </section>

        <div class="md3-list-group" v-if="vaultList.length > 0">
          <div
            v-for="item in vaultList"
            :key="item.path"
            class="md3-list-row"
            style="display: flex; align-items: center; gap: 10px;"
          >
            <div style="display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; cursor: pointer;" @click="openMedia(item.path)">
              <div class="icon-badge secondary">
                <Icons :name="getExtIcon(item.ext)" :size="16" />
              </div>
              <div style="min-width: 0; flex: 1;">
                <div
                  style="font-size: 12px; font-weight: 600; color: var(--on-surface); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; transition: filter 0.2s ease;"
                  :style="isVaultBlurred ? 'filter: blur(5px); user-select: none;' : ''"
                >
                  {{ item.name }}
                </div>
                <div style="font-size: 10px; color: var(--on-surface-variant); font-family: inherit; font-variant-numeric: tabular-nums; margin-top: 2px;">
                  <span style="color: var(--primary); font-weight: 500;">Vault/Stream · </span>{{ item.size }} · {{ (item.ext || '').toLowerCase() }}
                </div>
              </div>
            </div>

            <div style="display: flex; align-items: center; gap: 6px;">
              <button class="btn btn-icon" :disabled="openingPath === item.path" @click.stop="openMedia(item.path)" title="Play">
                <Icons name="play" :size="14" />
              </button>
              <button class="btn btn-icon" style="color: var(--error);" @click.stop="deleteVaultItem(item)" title="Delete">
                <Icons name="trash" :size="14" />
              </button>
            </div>
          </div>
        </div>

        <div v-else class="md3-card" style="text-align: center; padding: 28px 16px; opacity: 0.7;">
          <Icons name="lock" :size="28" style="color: var(--on-surface-variant); margin-bottom: 8px;" />
          <div style="font-size: 12px; font-weight: 600; color: var(--on-surface);">Vault is empty</div>
          <div style="font-size: 11px; color: var(--on-surface-variant); margin-top: 4px;">
            Downloads from stream links will be stored here securely
          </div>
        </div>
      </div>

      <div style="display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 28px 0 16px 0;">
        <div style="display: flex; align-items: center; gap: 12px; font-size: 11px;">
          <a href="https://t.me/noticesa" target="_blank" rel="noopener noreferrer" style="color: var(--on-surface-variant); text-decoration: none; display: flex; align-items: center; gap: 5px;">
            <Icons name="telegram" :size="13" />
            <span>@noticesa</span>
          </a>
          <span style="color: var(--outline-variant);">·</span>
          <a href="https://sociabuzz.com/noticesa/tribe" target="_blank" rel="noopener noreferrer" style="color: var(--primary); text-decoration: none; display: flex; align-items: center; gap: 5px; font-weight: 500;">
            <Icons name="heart" :size="13" style="color: #ff6b81;" />
            <span>Donate</span>
          </a>
        </div>
        <div style="font-size: 11px; opacity: 0.5;">
          HyperDL · Maintained by @noticesa
        </div>
      </div>

    </main>

    <transition name="toast-fade">
      <div v-if="toast.show" class="toast-pill" :class="toast.type">
        <Icons
          :name="toast.type === 'error' ? 'close' : (toast.type === 'success' ? 'check' : 'info')"
          :size="14"
          :style="toast.type === 'error' ? 'color: var(--error);' : (toast.type === 'success' ? 'color: var(--success);' : 'color: var(--primary);')"
        />
        <span>{{ toast.message }}</span>
      </div>
    </transition>

    <div v-if="showResolutionPicker" class="sheet-overlay" @click.self="closeResolutionPicker">
      <div class="sheet-panel">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 14px; font-weight: 600; color: var(--on-surface);">Select Resolution</span>
            <span class="badge-pill" style="font-size: 10px; padding: 2px 7px;">YouTube</span>
          </div>
          <button class="icon-btn" type="button" @click.stop="closeResolutionPicker">
            <Icons name="close" :size="18" />
          </button>
        </div>

        <!-- Scanning banner when probe is running (progressive stream detection) -->
        <div v-if="isProbingResolutions" style="display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--on-surface-variant); padding: 7px 10px; background: var(--surface-container-low); border: 1px solid var(--outline-variant); border-radius: 8px; margin-bottom: 10px;">
          <div class="spin-loader" style="display: flex; align-items: center;">
            <Icons name="refresh" :size="13" />
          </div>
          <span>Detecting real streams & exact file sizes...</span>
        </div>

        <!-- Loaded resolution list (instant presets smoothly updated to real streams) -->
        <div v-if="resolutions.length > 0" class="resolution-list">
          <button
            v-for="r in resolutions"
            :key="r.height || r.format_id"
            type="button"
            class="resolution-row"
            @click.stop="downloadWithResolution(r)"
          >
            <span class="res-label">
              <span class="res-badge">{{ r.badge || (r.height >= 720 ? (r.height >= 2160 ? '4K' : (r.height >= 1440 ? '2K' : 'HD')) : 'SD') }}</span>
              <span>{{ r.label || (r.height + 'p') }}</span>
              <span v-if="r.fps && r.fps > 30" class="fps-tag">{{ Math.round(r.fps) }}fps</span>
            </span>
            <span class="res-size">{{ formatFileSize(r.filesize) || r.desc || 'Preset' }}</span>
          </button>
        </div>

        <!-- Action buttons: Best Quality & Cancel -->
        <div style="display: flex; gap: 8px; margin-top: 12px;">
          <button class="btn btn-secondary" type="button" style="flex: 1; height: 38px; font-size: 12px;" @click.stop="downloadWithResolution(null)">
            Best Available Quality
          </button>
          <button class="btn btn-secondary" type="button" style="flex: 1; height: 38px; font-size: 12px; color: var(--error); border-color: rgba(255, 107, 107, 0.3);" @click.stop="closeResolutionPicker">
            Cancel
          </button>
        </div>
      </div>
    </div>

    <!-- Custom In-App Material 3 Confirmation Dialog -->
    <div v-if="confirmDialog.show" class="dialog-backdrop" @click.self="resolveConfirm(false)">
      <div class="dialog-card">
        <div class="dialog-title">{{ confirmDialog.title }}</div>
        <div class="dialog-message">{{ confirmDialog.message }}</div>
        <div class="dialog-actions">
          <button class="btn btn-secondary dialog-btn" type="button" @click.stop="resolveConfirm(false)">
            Cancel
          </button>
          <button
            class="btn dialog-btn"
            type="button"
            :style="confirmDialog.isDestructive ? 'background: var(--error); color: #fff; border-color: var(--error);' : 'background: var(--primary); color: var(--on-primary);'"
            @click.stop="resolveConfirm(true)"
          >
            {{ confirmDialog.confirmText }}
          </button>
        </div>
      </div>
    </div>

    <!-- In-App Quick Preview / Lightbox Modal -->
    <div v-if="previewModal.show" class="preview-backdrop" @click.self="closePreview">
      <div class="preview-card">
        <!-- Preview Top Bar -->
        <div class="preview-top-bar">
          <div class="preview-title-box">
            <div class="preview-filename">{{ previewModal.item?.name }}</div>
            <div class="preview-meta">
              {{ previewModal.item?.size }} · {{ (previewModal.item?.ext || '').toLowerCase() }}
              <span v-if="previewImagesList.length > 1 && previewModal.isImage">
                · {{ currentImageIndex + 1 }} of {{ previewImagesList.length }}
              </span>
            </div>
          </div>
          <button class="btn btn-icon preview-close-btn" @click="closePreview" title="Close">
            <Icons name="close" :size="16" />
          </button>
        </div>

        <!-- Preview Body -->
        <div class="preview-body">
          <div v-if="previewLoading" class="preview-center-box">
            <div class="spinner"></div>
            <div style="font-size: 12px; color: var(--on-surface-variant); margin-top: 10px;">Loading preview...</div>
          </div>

          <div v-else-if="previewModal.isImage && previewData" class="preview-image-container">
            <img :src="previewData" class="preview-image" :alt="previewModal.item?.name" />
            
            <button
              v-if="previewImagesList.length > 1"
              class="preview-nav-btn prev"
              :disabled="currentImageIndex <= 0"
              @click="navigatePreview(-1)"
              title="Previous"
            >
              <Icons name="chevron-left" :size="20" />
            </button>
            <button
              v-if="previewImagesList.length > 1"
              class="preview-nav-btn next"
              :disabled="currentImageIndex >= previewImagesList.length - 1"
              @click="navigatePreview(1)"
              title="Next"
            >
              <Icons name="chevron-right" :size="20" />
            </button>
          </div>

          <div v-else class="preview-center-box">
            <div class="icon-badge secondary" style="width: 48px; height: 48px; margin-bottom: 12px;">
              <Icons name="image" :size="24" />
            </div>
            <div style="font-size: 13px; font-weight: 600; color: var(--on-surface);">
              {{ previewError || 'Preview not available' }}
            </div>
            <div style="font-size: 11px; color: var(--on-surface-variant); margin-top: 4px;">
              Tap 'Open in app' to view in gallery
            </div>
          </div>
        </div>

        <!-- Preview Bottom Actions -->
        <div class="preview-bottom-bar">
          <button class="btn btn-secondary" style="padding: 8px 14px; font-size: 12px; gap: 6px;" @click="openMedia(previewModal.item?.path)">
            <Icons name="external-link" :size="14" />
            <span>Open in app</span>
          </button>
          <button class="btn btn-secondary" style="padding: 8px 14px; font-size: 12px; color: var(--error); gap: 6px;" @click="deleteFromPreview">
            <Icons name="trash" :size="14" />
            <span>Delete</span>
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { execCommand, openMediaFile, openFolder, base64EncodeUtf8, base64DecodeUtf8 } from '@/helpers/shell.js'
import Icons from '@/components/Icons.vue'

const activeTab = ref('download')
const url = ref('')
const urlInput = ref(null)
const terminalCard = ref(null)
const selectedFormat = ref('video')
const isProcessing = ref(false)
const autoDl = ref(false)
const storageFree = ref('')
const toast = ref({ show: false, message: '', type: 'info' })
const isOnline = ref(typeof navigator !== 'undefined' && 'onLine' in navigator ? navigator.onLine : true)

const resolutions = ref([])
const showResolutionPicker = ref(false)
const isProbingResolutions = ref(false)
const pendingUrl = ref('')
const cookiesText = ref('')
const cookiesActive = ref(false)
const cookiesLines = ref(0)

const detectedClipUrl = ref('')
const lastDismissedClipUrl = ref('')

const storageStats = ref({
  media_count: 0,
  media_bytes: 0,
  media_size: '0 B',
  junk_count: 0,
  junk_bytes: 0,
  junk_size: '0 B',
  free_bytes: 0,
  free_size: '',
  total_bytes: 0,
  total_size: ''
})
const isCleaningJunk = ref(false)

const searchQuery = ref('')
const selectedCategory = ref('all')

const previewModal = ref({
  show: false,
  item: null,
  isImage: false,
  isMedia: false,
  isVideo: false,
  isAudio: false
})
const previewData = ref('')
const previewLoading = ref(false)
const previewError = ref('')

const sysInfo = ref({ python: '', storage_free: '' })
const ytdlpInfo = ref({ current: '', latest: '', has_update: false })
const ytdlpChecking = ref(false)
const ytdlpUpdating = ref(false)

const ytdlpButtonLabel = computed(() => {
  if (ytdlpChecking.value) return 'Checking...'
  if (ytdlpUpdating.value) return 'Updating...'
  if (ytdlpInfo.value.has_update) return `Update to ${ytdlpInfo.value.latest}`
  if (ytdlpInfo.value.latest) return 'Up to date'
  return 'Check update'
})

async function handleYtdlpAction() {
  if (ytdlpInfo.value.has_update) {
    ytdlpUpdating.value = true
    try {
      const raw = await runBridge('update_ytdlp')
      if (raw && raw.startsWith('{')) {
        const res = JSON.parse(raw)
        if (res.success) {
          ytdlpInfo.value.current = res.version
          ytdlpInfo.value.latest = res.version
          ytdlpInfo.value.has_update = false
          showToast(`yt-dlp updated to ${res.version}`)
        } else {
          showToast(res.error || 'Update failed', 'error')
        }
      } else {
        showToast('Update failed: invalid response', 'error')
      }
    } catch (e) {
      showToast('Update failed: ' + String(e), 'error')
    } finally {
      ytdlpUpdating.value = false
    }
  } else {
    ytdlpChecking.value = true
    try {
      const raw = await runBridge('check_ytdlp')
      if (raw && raw.startsWith('{')) {
        const res = JSON.parse(raw)
        if (res.current) {
          ytdlpInfo.value = res
          if (res.has_update) {
            showToast(`yt-dlp update available: ${res.latest}`)
          } else {
            showToast(`yt-dlp is up to date (${res.current})`)
          }
        } else if (res.error) {
          showToast(res.error, 'error')
        }
      } else {
        showToast('Check failed: invalid response', 'error')
      }
    } catch (e) {
      showToast('Failed to check yt-dlp update', 'error')
    } finally {
      ytdlpChecking.value = false
    }
  }
}

const logContent = ref('Loading console log...')

const confirmDialog = ref({
  show: false,
  title: 'Confirm',
  message: '',
  confirmText: 'Confirm',
  isDestructive: true,
  resolve: null
})

function showConfirm({ title = 'Confirm', message = '', confirmText = 'Confirm', isDestructive = true }) {
  return new Promise((resolve) => {
    confirmDialog.value = {
      show: true,
      title,
      message,
      confirmText,
      isDestructive,
      resolve
    }
  })
}

function resolveConfirm(result) {
  const cb = confirmDialog.value.resolve
  confirmDialog.value.show = false
  confirmDialog.value.resolve = null
  if (cb) {
    cb(result)
  }
}

let toastTimer = null
let pollTimer = null
let isPollingActive = false

const task = ref({
  status: 'idle',
  percent: 0,
  speed: '',
  downloaded: '',
  total: '',
  title: '',
  file_path: '',
  error: '',
  url: '',
  fmt: 'video',
  format_id: '',
  height: ''
})

function saveActiveTaskToStorage(t) {
  try {
    if (!t || t.status === 'idle' || t.status === 'completed') {
      localStorage.removeItem('hyperdl_active_task')
    } else {
      localStorage.setItem('hyperdl_active_task', JSON.stringify({
        status: t.status,
        percent: t.percent || 0,
        downloaded: t.downloaded || '',
        total: t.total || '',
        speed: t.speed || '',
        title: t.title || '',
        url: t.url || url.value,
        fmt: t.fmt || selectedFormat.value,
        format_id: t.format_id || '',
        height: t.height || '',
        error: t.error || ''
      }))
    }
  } catch (e) {}
}

function loadActiveTaskFromStorage() {
  try {
    const raw = localStorage.getItem('hyperdl_active_task')
    if (raw) {
      const parsed = JSON.parse(raw)
      if (parsed && parsed.status !== 'completed' && parsed.status !== 'idle') {
        return parsed
      }
    }
  } catch (e) {}
  return null
}

const historyList = ref([])
const isVaultActive = ref(false)
const isVaultBlurred = ref(true)
const vaultList = ref([])

let versionClickCount = 0
let versionClickTimer = null

async function onVersionClick() {
  versionClickCount++
  if (versionClickTimer) clearTimeout(versionClickTimer)
  versionClickTimer = setTimeout(() => {
    versionClickCount = 0
  }, 2500)

  if (versionClickCount >= 5) {
    versionClickCount = 0
    try {
      const res = await runBridge('toggle_vault')
      const data = JSON.parse(res)
      isVaultActive.value = !!data.vault_enabled
      if (isVaultActive.value) {
        showToast('Vault Mode: Active', 'success')
        activeTab.value = 'vault'
        await fetchVaultHistory()
      } else {
        showToast('Vault Mode: Deactivated', 'info')
        if (activeTab.value === 'vault') {
          activeTab.value = 'download'
        }
      }
    } catch (e) {
      showToast('Toggle failed', 'error')
    }
  }
}

async function checkVaultStatus() {
  try {
    const raw = await runBridge('get_vault_status')
    if (raw) {
      const data = JSON.parse(raw)
      isVaultActive.value = !!data.vault_enabled
      if (isVaultActive.value && activeTab.value === 'vault') {
        fetchVaultHistory()
      }
    }
  } catch (e) {}
}

async function fetchVaultHistory() {
  try {
    const raw = await runBridge('list', 'vault')
    if (raw && raw.startsWith('[')) {
      const list = JSON.parse(raw)
      list.sort((a, b) => (b.mtime || 0) - (a.mtime || 0))
      vaultList.value = list
    }
  } catch (e) {}
}

async function deleteVaultItem(item) {
  const prevList = [...vaultList.value]
  vaultList.value = vaultList.value.filter(i => i.path !== item.path)
  try {
    const res = await runBridge('delete', item.path)
    const data = JSON.parse(res)
    if (!data.success) {
      vaultList.value = prevList
      showToast('Gagal menghapus: ' + (data.error || 'unknown'), 'error')
    } else {
      showToast('File vault dihapus', 'success')
    }
  } catch (e) {
    vaultList.value = prevList
    showToast('Gagal menghapus', 'error')
  }
}

function showToast(message, type = 'info') {
  toast.value = { show: true, message, type }
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value.show = false
  }, 2600)
}

const supportedPlatforms = [
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

const detectedPlatform = computed(() => {
  const u = url.value.toLowerCase()
  if (u.includes('tiktok.com') || u.includes('douyin.com')) return { name: 'TikTok', id: 'tiktok' }
  if (u.includes('instagram.com') || u.includes('instagr.am')) return { name: 'Instagram', id: 'instagram' }
  if (u.includes('twitter.com') || u.includes('x.com') || u.includes('t.co')) return { name: 'X', id: 'x' }
  if (u.includes('youtube.com') || u.includes('youtu.be')) return { name: 'YouTube', id: 'youtube' }
  if (u.includes('facebook.com') || u.includes('fb.watch') || u.includes('fb.com')) return { name: 'Facebook', id: 'facebook' }
  if (u.includes('reddit.com') || u.includes('redd.it')) return { name: 'Reddit', id: 'reddit' }
  if (u.includes('pinterest.com') || u.includes('pin.it')) return { name: 'Pinterest', id: 'pinterest' }
  if (u.includes('bsky.app')) return { name: 'Bluesky', id: 'bluesky' }
  if (u.includes('threads.net')) return { name: 'Threads', id: 'threads' }
  if (u.includes('bilibili.com') || u.includes('b23.tv')) return { name: 'Bilibili', id: 'bilibili' }
  if (u.includes('streamable.com')) return { name: 'Streamable', id: 'streamable' }
  return { name: 'Direct link', id: 'link' }
})

function isNetworkError(err) {
  if (!err) return false
  if (!isOnline.value) return true
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

function formatErrorMessage(err) {
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

function formatProgressInfo(t) {
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

function formatSpeedInfo(t) {
  if (!t) return ''
  const spd = String(t.speed || '').trim()
  if (spd && spd !== 'N/A' && spd !== 'NA' && spd !== 'None' && spd !== 'null') {
    return spd
  }
  if (t.status === 'paused') {
    return `${t.percent || 0}% ready`
  }
  return ''
}

function handleOnline() {
  isOnline.value = true
  showToast('Internet connection restored', 'success')
  if (task.value.status === 'paused') {
    showToast('Network restored: Tap Resume to continue', 'info')
  }
}

function handleOffline() {
  isOnline.value = false
  // Never kill/pause running background downloads on transient WebView offline events.
  // The backend downloader has built-in retry and socket timeout logic.
  showToast('Network connection unstable', 'warning')
}

function testConnectivity() {
  if (typeof navigator !== 'undefined' && navigator.onLine) {
    isOnline.value = true
    showToast('Network is online. Ready to download.', 'success')
  } else {
    isOnline.value = false
    showToast('Device is still offline. Please check your connection.', 'warning')
  }
}

const taskStatusTitle = computed(() => {
  switch (task.value.status) {
    case 'resolving': return 'Connecting...'
    case 'downloading': return 'Downloading...'
    case 'paused': return 'Download paused'
    case 'completed': return 'Download complete'
    case 'error': return isNetworkError(task.value.error) ? 'Network disconnected (Paused)' : 'Download failed'
    default: return 'Ready'
  }
})

function getExtIcon(ext) {
  const e = (ext || '').toLowerCase()
  if (['mp4', 'mkv', 'webm', 'mov', 'avi'].includes(e)) return 'video'
  if (['flac', 'wav', 'mp3', 'm4a', 'aac', 'ogg', 'opus'].includes(e)) return 'music'
  return 'image'
}

function shellEscape(arg) {
  return "'" + String(arg).replace(/'/g, "'\\''") + "'"
}

function extractUrl(text) {
  if (!text) return ''
  const match = String(text).match(/https?:\/\/[^\s<>"]+/)
  return match ? match[0].trim() : text.trim()
}

function onPasteInput() {
  setTimeout(() => {
    if (url.value) {
      url.value = extractUrl(url.value)
    }
  }, 50)
}

function onUrlInput() {
  if (url.value && (url.value.includes('\n') || url.value.includes(' '))) {
    const clean = extractUrl(url.value)
    if (clean && clean !== url.value) {
      url.value = clean
    }
  }
}

function dismissTask() {
  saveActiveTaskToStorage(null)
  task.value = {
    status: 'idle',
    percent: 0,
    speed: '',
    downloaded: '',
    total: '',
    title: '',
    file_path: '',
    error: '',
    url: '',
    fmt: 'video',
    format_id: '',
    height: ''
  }
}

async function runBridge(action, ...args) {
  const safeAction = shellEscape(action)
  const safeParams = args.map(shellEscape).join(' ')
  const cmd = `if [ -x /data/adb/modules/hyperdl/system/bin/libhyperdl.so ]; then /data/adb/modules/hyperdl/system/bin/libhyperdl.so ${safeAction} ${safeParams}; elif [ -x /system/bin/libhyperdl.so ]; then /system/bin/libhyperdl.so ${safeAction} ${safeParams}; elif [ -x /data/adb/modules_update/hyperdl/system/bin/libhyperdl.so ]; then /data/adb/modules_update/hyperdl/system/bin/libhyperdl.so ${safeAction} ${safeParams}; elif [ -x /data/data/com.termux/files/home/HyperDL_Module/system/bin/libhyperdl.so ]; then /data/data/com.termux/files/home/HyperDL_Module/system/bin/libhyperdl.so ${safeAction} ${safeParams}; else echo "binary_not_found"; fi`
  
  const timeoutMs = action === 'probe' ? 50000 : 15000
  const res = await execCommand(cmd, timeoutMs)
  return (res || '').trim()
}

async function pasteClipboard() {
  if (urlInput.value) {
    urlInput.value.focus()
  }

  let text = ''
  if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.readText) {
    try {
      text = await navigator.clipboard.readText()
    } catch (e) {}
  }

  if (!text) {
    try {
      if (urlInput.value) {
        urlInput.value.focus()
        urlInput.value.select()
        const ok = document.execCommand('paste')
        if (ok && urlInput.value.value) {
          text = urlInput.value.value
        }
      }
    } catch (e) {}
  }

  if (!text) {
    try {
      if (urlInput.value) {
        urlInput.value.focus()
        urlInput.value.select()
        await execCommand('input keyevent 279', 2000)
        await new Promise(resolve => setTimeout(resolve, 150))
        if (urlInput.value.value) {
          text = urlInput.value.value
        }
      }
    } catch (e) {}
  }

  if (!text) {
    try {
      const raw = await runBridge('get_clipboard')
      if (raw && raw.startsWith('{')) {
        const parsed = JSON.parse(raw)
        if (parsed.clipboard_b64) {
          text = base64DecodeUtf8(parsed.clipboard_b64)
        }
      }
    } catch (e) {}
  }

  if (text && text.trim()) {
    url.value = extractUrl(text)
    showToast('Link pasted', 'success')
    return
  }

  if (urlInput.value) {
    urlInput.value.focus()
  }
  showToast('Tap & hold input box to paste', 'info')
}

const STANDARD_RESOLUTIONS = [
  { height: 2160, format_id: '2160', label: '2160p (4K Ultra HD)', badge: '4K', desc: 'Ultra HD', ext: 'mp4' },
  { height: 1440, format_id: '1440', label: '1440p (2K QHD)', badge: '2K', desc: 'Quad HD', ext: 'mp4' },
  { height: 1080, format_id: '1080', label: '1080p Full HD', badge: 'FHD', desc: 'Recommended', ext: 'mp4' },
  { height: 720, format_id: '720', label: '720p HD', badge: 'HD', desc: 'Fast & Crisp', ext: 'mp4' },
  { height: 480, format_id: '480', label: '480p SD', badge: 'SD', desc: 'Standard', ext: 'mp4' },
  { height: 360, format_id: '360', label: '360p Data Saver', badge: 'SD', desc: 'Data Saver', ext: 'mp4' }
]

function needsResolutionPicker(u) {
  const l = u.toLowerCase()
  return l.includes('youtube.com') || l.includes('youtu.be')
}

function formatFileSize(bytes) {
  if (!bytes || bytes <= 0) return ''
  if (bytes >= 1024 * 1024 * 1024) return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB'
  if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(0) + ' MB'
  return (bytes / 1024).toFixed(0) + ' KB'
}

let probeTimer = null

function closeResolutionPicker() {
  showResolutionPicker.value = false
  isProbingResolutions.value = false
  if (probeTimer) {
    clearTimeout(probeTimer)
    probeTimer = null
  }
}

async function startDownload() {
  if (!url.value.trim() || isProcessing.value) return

  if (!isOnline.value) {
    showToast('No internet connection. Connect to Wi-Fi or mobile data.', 'warning')
    return
  }

  const clean = extractUrl(url.value)
  url.value = clean
  const u = clean

  if (selectedFormat.value === 'video' && needsResolutionPicker(u)) {
    pendingUrl.value = u
    resolutions.value = [...STANDARD_RESOLUTIONS]
    showResolutionPicker.value = true
    isProbingResolutions.value = true

    if (probeTimer) clearTimeout(probeTimer)
    // Decoupled probe: fire AFTER sheet slide-up animation completes (250ms)
    // Child process runs with nice(19) so WebView rendering is 100% fluid
    probeTimer = setTimeout(() => {
      runBridge('probe', u).then((raw) => {
        if (!showResolutionPicker.value || pendingUrl.value !== u) return
        let parsed = null
        try {
          const jsonMatch = (raw || '').match(/\[[\s\S]*\]|\{[\s\S]*\}/)
          parsed = jsonMatch ? JSON.parse(jsonMatch[0]) : JSON.parse(raw)
        } catch (e) {}

        const list = Array.isArray(parsed) ? parsed : (parsed && parsed.resolutions ? parsed.resolutions : null)
        if (list && list.length > 0) {
          resolutions.value = list
        }
      }).catch(() => {}).finally(() => {
        if (pendingUrl.value === u) {
          isProbingResolutions.value = false
        }
      })
    }, 250)
    return
  }

  await doDownload(u, selectedFormat.value, null)
}

async function downloadWithResolution(r) {
  showResolutionPicker.value = false
  isProbingResolutions.value = false
  if (probeTimer) {
    clearTimeout(probeTimer)
    probeTimer = null
  }
  let extraArg = null
  if (r && r.height) {
    extraArg = `--height=${r.height}`
  } else if (r && r.format_id) {
    extraArg = `--format-id=${r.format_id}`
  }
  await doDownload(pendingUrl.value, selectedFormat.value, extraArg)
}

async function pauseDownload(reason = '') {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  isProcessing.value = false
  task.value.status = 'paused'
  if (reason) {
    task.value.error = reason
  }
  saveActiveTaskToStorage(task.value)
  try {
    await runBridge('pause')
  } catch (e) {}
  showToast(reason ? `Paused: ${reason}` : 'Download paused', 'info')
  fetchLogs()
}

async function resumeDownload() {
  if (isProcessing.value) return
  if (!isOnline.value) {
    showToast('No internet connection. Connect to Wi-Fi or mobile data.', 'warning')
    return
  }
  const targetUrl = task.value.url || url.value
  if (!targetUrl) {
    showToast('No download URL found to resume', 'error')
    return
  }
  if (!url.value) {
    url.value = targetUrl
  }
  const fmt = task.value.fmt || selectedFormat.value || 'video'
  let extraArg = null
  if (task.value.height) {
    extraArg = `--height=${task.value.height}`
  } else if (task.value.format_id) {
    extraArg = `--format-id=${task.value.format_id}`
  }
  showToast('Resuming download...', 'info')
  await doDownload(targetUrl, fmt, extraArg, true /* isResume */)
}

async function cancelDownload() {
  try {
    await runBridge('cancel')
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    task.value = {
      status: 'idle',
      percent: 0,
      speed: '',
      downloaded: '',
      total: '',
      title: '',
      file_path: '',
      error: '',
      url: '',
      fmt: 'video',
      format_id: '',
      height: ''
    }
    saveActiveTaskToStorage(null)
    isProcessing.value = false
    showToast('Download cancelled', 'info')
    fetchLogs()
  } catch (e) {
    showToast('Failed to cancel download', 'error')
  }
}

async function doDownload(u, fmt, extraArg, isResume = false) {
  isProcessing.value = true
  let fid = ''
  let ht = ''
  if (extraArg) {
    if (extraArg.startsWith('--format-id=')) fid = extraArg.replace('--format-id=', '')
    if (extraArg.startsWith('--height=')) ht = extraArg.replace('--height=', '')
  }

  if (isResume) {
    task.value.status = 'resolving'
    task.value.error = ''
    task.value.url = u
    task.value.fmt = fmt
    if (fid) task.value.format_id = fid
    if (ht) task.value.height = ht
  } else {
    task.value = {
      status: 'resolving',
      percent: 5,
      speed: '',
      downloaded: '',
      total: '',
      title: u,
      file_path: '',
      error: '',
      url: u,
      fmt: fmt,
      format_id: fid,
      height: ht
    }
  }
  saveActiveTaskToStorage(task.value)

  showToast(isResume ? 'Resuming download...' : 'Starting download...', 'info')
  try {
    if (extraArg) {
      await runBridge('download', u, fmt, extraArg)
    } else {
      await runBridge('download', u, fmt)
    }
    startPolling()
  } catch (e) {
    task.value.status = 'error'
    task.value.error = String(e)
    isProcessing.value = false
    saveActiveTaskToStorage(task.value)
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer)
  const pollStart = Date.now()
  pollTimer = setInterval(async () => {
    if (isPollingActive) return
    isPollingActive = true
    try {
      const raw = await runBridge('status')
      if (!raw) return
      if (raw === 'binary_not_found') {
        clearInterval(pollTimer)
        pollTimer = null
        isProcessing.value = false
        task.value.status = 'error'
        task.value.error = 'HyperDL binary not found. If you just installed the module, please reboot your device.'
        showToast('Module not activated: Reboot required', 'error')
        return
      }
      
      let parsed = null
      try {
        parsed = JSON.parse(raw)
      } catch (e) {
        return
      }
      if (!parsed || typeof parsed !== 'object') return

      task.value = { ...task.value, ...parsed }
      saveActiveTaskToStorage(task.value)

      if (parsed.status === 'completed') {
        clearInterval(pollTimer)
        pollTimer = null
        isProcessing.value = false
        saveActiveTaskToStorage(null)
        showToast('Download complete', 'success')
        fetchHistory()
        fetchLogs()
      } else if (parsed.status === 'paused') {
        clearInterval(pollTimer)
        pollTimer = null
        isProcessing.value = false
        saveActiveTaskToStorage(task.value)
        showToast('Download paused', 'info')
        fetchLogs()
      } else if (parsed.status === 'error') {
        clearInterval(pollTimer)
        pollTimer = null
        isProcessing.value = false
        saveActiveTaskToStorage(task.value)
        const isNet = isNetworkError(parsed.error)
        showToast(isNet ? 'Network disconnected: Ready to resume' : (parsed.error || 'Download failed'), 'error')
        fetchLogs()
      } else if (parsed.status === 'idle') {
        clearInterval(pollTimer)
        pollTimer = null
        isProcessing.value = false
        saveActiveTaskToStorage(null)
      } else if (parsed.status === 'resolving' && (Date.now() - pollStart > 50000)) {
        clearInterval(pollTimer)
        pollTimer = null
        isProcessing.value = false
        task.value.status = 'error'
        task.value.error = 'Connection timed out while resolving media. Platform may be slow or blocking requests.'
        showToast('Download timed out', 'error')
        saveActiveTaskToStorage(task.value)
        fetchLogs()
      }
    } catch (e) {
    } finally {
      isPollingActive = false
    }
  }, 400)
}

const selectedFiles = ref(new Set())

const isAllSelected = computed(() => {
  return historyList.value.length > 0 && selectedFiles.value.size === historyList.value.length
})

function toggleSelect(path) {
  const s = new Set(selectedFiles.value)
  if (s.has(path)) {
    s.delete(path)
  } else {
    s.add(path)
  }
  selectedFiles.value = s
}

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedFiles.value = new Set()
  } else {
    selectedFiles.value = new Set(historyList.value.map(i => i.path))
  }
}

function clearSelection() {
  selectedFiles.value = new Set()
}

function handleItemClick(item) {
  if (selectedFiles.value.size > 0) {
    toggleSelect(item.path)
  } else if (isImageExt(item.ext)) {
    openPreview(item)
  } else {
    openMedia(item.path)
  }
}

async function deleteSelected() {
  const count = selectedFiles.value.size
  if (count === 0) return
  const ok = await showConfirm({
    title: 'Delete Media',
    message: `Are you sure you want to delete ${count} selected media file${count > 1 ? 's' : ''}?`,
    confirmText: 'Delete',
    isDestructive: true
  })
  if (!ok) return

  const paths = Array.from(selectedFiles.value)
  const prevList = [...historyList.value]
  const toDeleteSet = new Set(paths)
  historyList.value = historyList.value.filter(i => !toDeleteSet.has(i.path))
  selectedFiles.value = new Set()

  try {
    await runBridge('delete', ...paths)
    showToast(`Deleted ${paths.length} file${paths.length > 1 ? 's' : ''}`, 'success')
    fetchHistory()
  } catch (e) {
    historyList.value = prevList
    showToast('Failed to delete selected files', 'error')
    fetchHistory()
  }
}

async function fetchHistory() {
  try {
    const raw = await runBridge('list')
    if (raw && raw.startsWith('[')) {
      const list = JSON.parse(raw)
      list.sort((a, b) => (b.mtime || 0) - (a.mtime || 0))
      historyList.value = list
      const currentPaths = new Set(historyList.value.map(i => i.path))
      selectedFiles.value = new Set([...selectedFiles.value].filter(p => currentPaths.has(p)))
      fetchStorageStats()
    }
  } catch (e) {}
}

function isVideoExt(ext) {
  const e = (ext || '').toLowerCase()
  return ['mp4', 'mkv', 'webm', 'mov', 'avi', 'flv'].includes(e)
}

function isImageExt(ext) {
  const e = (ext || '').toLowerCase()
  return ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'].includes(e)
}

function isAudioExt(ext) {
  const e = (ext || '').toLowerCase()
  return ['mp3', 'm4a', 'aac', 'ogg', 'flac', 'wav', 'opus'].includes(e)
}

const videoCount = computed(() => historyList.value.filter(i => isVideoExt(i.ext)).length)
const imageCount = computed(() => historyList.value.filter(i => isImageExt(i.ext)).length)
const audioCount = computed(() => historyList.value.filter(i => isAudioExt(i.ext)).length)

const filteredHistoryList = computed(() => {
  let list = historyList.value
  if (selectedCategory.value === 'video') {
    list = list.filter(i => isVideoExt(i.ext))
  } else if (selectedCategory.value === 'image') {
    list = list.filter(i => isImageExt(i.ext))
  } else if (selectedCategory.value === 'audio') {
    list = list.filter(i => isAudioExt(i.ext))
  }

  const q = (searchQuery.value || '').trim().toLowerCase()
  if (q) {
    list = list.filter(i => (i.name || '').toLowerCase().includes(q) || (i.folder || '').toLowerCase().includes(q))
  }
  return list
})

function clearSearchAndFilter() {
  searchQuery.value = ''
  selectedCategory.value = 'all'
}

const storageBarPercent = computed(() => {
  if (!storageStats.value.total_bytes || storageStats.value.total_bytes <= 0) return 0
  const used = storageStats.value.total_bytes - storageStats.value.free_bytes
  const pct = (used / storageStats.value.total_bytes) * 100
  return Math.min(Math.max(pct, 2), 100).toFixed(1)
})

async function fetchStorageStats() {
  try {
    const raw = await runBridge('storage_info')
    if (raw && raw.startsWith('{')) {
      storageStats.value = JSON.parse(raw)
      if (storageStats.value.free_size) {
        storageFree.value = storageStats.value.free_size
      }
    }
  } catch (e) {}
}

async function cleanJunk() {
  if (isCleaningJunk.value) return
  isCleaningJunk.value = true
  try {
    const raw = await runBridge('clean_junk')
    if (raw && raw.startsWith('{')) {
      const res = JSON.parse(raw)
      if (res.deleted > 0) {
        showToast(`Cleaned ${res.deleted} junk file${res.deleted > 1 ? 's' : ''} (${res.freed_size} freed)`, 'success')
      } else {
        showToast('Storage is clean! No junk files found.', 'info')
      }
    }
    await fetchStorageStats()
    await fetchHistory()
  } catch (e) {
    showToast('Failed to clean storage', 'error')
  } finally {
    isCleaningJunk.value = false
  }
}

function formatTruncatedUrl(u) {
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

async function checkClipboardSniffer() {
  let text = ''
  if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.readText) {
    try {
      text = await navigator.clipboard.readText()
    } catch (e) {}
  }

  if (!text) {
    try {
      const raw = await runBridge('get_clipboard')
      if (raw && raw.startsWith('{')) {
        const parsed = JSON.parse(raw)
        if (parsed.clipboard_b64) {
          text = base64DecodeUtf8(parsed.clipboard_b64)
        }
      }
    } catch (e) {}
  }

  if (!text) return
  const foundUrl = extractUrl(text)
  if (foundUrl && foundUrl.startsWith('http') && foundUrl !== url.value && foundUrl !== (task.value && task.value.url) && foundUrl !== lastDismissedClipUrl.value) {
    detectedClipUrl.value = foundUrl
  } else if (foundUrl === url.value || (task.value && foundUrl === task.value.url)) {
    detectedClipUrl.value = ''
  }
}

function onVisibilityChange() {
  if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
    checkClipboardSniffer()
  }
}

function applyClipUrl(autoStart = false) {
  if (detectedClipUrl.value) {
    url.value = detectedClipUrl.value
    detectedClipUrl.value = ''
    if (autoStart) {
      nextTick(() => {
        startDownload()
      })
    }
  }
}

function dismissClipUrl() {
  lastDismissedClipUrl.value = detectedClipUrl.value
  detectedClipUrl.value = ''
}

const previewImagesList = computed(() => {
  return filteredHistoryList.value.filter(i => isImageExt(i.ext))
})

const currentImageIndex = computed(() => {
  if (!previewModal.value.item || !previewModal.value.isImage) return -1
  return previewImagesList.value.findIndex(i => i.path === previewModal.value.item.path)
})

async function openPreview(item) {
  if (!item || !item.path) return
  const ext = (item.ext || '').toLowerCase()
  if (!isImageExt(ext)) {
    openMedia(item.path)
    return
  }

  previewModal.value = {
    show: true,
    item,
    isImage: true
  }
  previewData.value = ''
  previewError.value = ''
  previewLoading.value = true

  try {
    const raw = await runBridge('preview', item.path)
    if (raw && raw.startsWith('{')) {
      const res = JSON.parse(raw)
      if (res.success && res.data) {
        previewData.value = res.data
      } else if (res.error === 'too_large') {
        previewError.value = `File size is ${res.size || item.size}. Tap 'Open in app' to view.`
      } else {
        previewError.value = 'Preview not available for this image.'
      }
    } else {
      previewError.value = 'Could not generate preview.'
    }
  } catch (e) {
    previewError.value = 'Failed to load preview.'
  } finally {
    previewLoading.value = false
  }
}

function closePreview() {
  previewModal.value.show = false
  previewModal.value.item = null
  previewData.value = ''
  previewError.value = ''
}

function navigatePreview(direction) {
  const list = previewImagesList.value
  const curIdx = currentImageIndex.value
  if (curIdx === -1 || list.length <= 1) return
  const nextIdx = curIdx + direction
  if (nextIdx >= 0 && nextIdx < list.length) {
    openPreview(list[nextIdx])
  }
}

async function deleteFromPreview() {
  const item = previewModal.value.item
  if (!item) return
  closePreview()
  await deleteItem(item)
}

const cookieAccounts = computed(() => {
  const text = (cookiesText.value || '').toLowerCase()
  const raw = cookiesText.value || ''

  let igActive = text.includes('instagram.com') && (text.includes('sessionid') || text.includes('ds_user_id'))
  let igDetail = 'Not configured'
  if (igActive) {
    const idMatch = raw.match(/ds_user_id\s+([0-9]+)/i) || raw.match(/ds_user_id=([0-9]+)/i)
    igDetail = idMatch ? `User ID: ${idMatch[1]}` : 'Session active'
  }

  let ttActive = text.includes('tiktok.com') && (text.includes('sessionid') || text.includes('mstoken'))
  let ttDetail = ttActive ? 'Session active' : 'Not configured'

  let ytActive = (text.includes('youtube.com') || text.includes('google.com')) && (text.includes('login_info') || text.includes('sapisid') || text.includes('sid'))
  let ytDetail = ytActive ? 'Session active' : 'Not configured'

  let xActive = (text.includes('twitter.com') || text.includes('x.com')) && (text.includes('auth_token') || text.includes('ct0'))
  let xDetail = xActive ? 'Auth token active' : 'Not configured'

  let fbActive = text.includes('facebook.com') && (text.includes('c_user') || text.includes('xs'))
  let fbDetail = 'Not configured'
  if (fbActive) {
    const fbMatch = raw.match(/c_user\s+([0-9]+)/i) || raw.match(/c_user=([0-9]+)/i)
    fbDetail = fbMatch ? `User ID: ${fbMatch[1]}` : 'Session active'
  }

  let pinActive = text.includes('pinterest.com') && (text.includes('_auth') || text.includes('_pinterest_sess'))
  let pinDetail = pinActive ? 'Session active' : 'Not configured'

  let redditActive = text.includes('reddit.com') && text.includes('reddit_session')
  let redditDetail = redditActive ? 'Session active' : 'Not configured'

  return [
    { id: 'instagram', name: 'Instagram', icon: 'instagram', active: igActive, detail: igDetail },
    { id: 'tiktok', name: 'TikTok', icon: 'tiktok', active: ttActive, detail: ttDetail },
    { id: 'youtube', name: 'YouTube', icon: 'youtube', active: ytActive, detail: ytDetail },
    { id: 'x', name: 'X (Twitter)', icon: 'x', active: xActive, detail: xDetail },
    { id: 'facebook', name: 'Facebook', icon: 'facebook', active: fbActive, detail: fbDetail },
    { id: 'pinterest', name: 'Pinterest', icon: 'pinterest', active: pinActive, detail: pinDetail },
    { id: 'reddit', name: 'Reddit', icon: 'reddit', active: redditActive, detail: redditDetail }
  ]
})

async function deleteItem(item) {
  const ok = await showConfirm({
    title: 'Delete File',
    message: `Are you sure you want to delete "${item.name}"?`,
    confirmText: 'Delete',
    isDestructive: true
  })
  if (!ok) return

  const prevList = [...historyList.value]
  historyList.value = historyList.value.filter(i => i.path !== item.path)
  const s = new Set(selectedFiles.value)
  s.delete(item.path)
  selectedFiles.value = s

  try {
    await runBridge('delete', item.path)
    showToast('File deleted', 'success')
    fetchHistory()
  } catch (e) {
    historyList.value = prevList
    showToast('Failed to delete file', 'error')
    fetchHistory()
  }
}

const openingPath = ref(null)
const openingFolder = ref(false)

async function openMedia(filePath) {
  if (!filePath || openingPath.value) return
  openingPath.value = filePath
  showToast('Opening media...', 'info')
  try {
    await openMediaFile(filePath)
  } catch (e) {
    showToast('Failed to open media', 'error')
  } finally {
    openingPath.value = null
  }
}

async function openMediaFolder() {
  if (openingFolder.value) return
  openingFolder.value = true
  showToast('Opening folder...', 'info')
  try {
    await openFolder()
  } catch (e) {
    showToast('Failed to open folder', 'error')
  } finally {
    openingFolder.value = false
  }
}

async function toggleAutoDl() {
  const nextState = !autoDl.value
  autoDl.value = nextState
  try {
    await runBridge('toggle_autodl', nextState ? '1' : '0')
    showToast(nextState ? 'Clipboard monitor enabled' : 'Clipboard monitor disabled', 'success')
  } catch (e) {
    autoDl.value = !nextState
    showToast('Failed to update setting', 'error')
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
      showToast('Cookies saved', 'success')
    }
  } catch (e) {
    showToast('Failed to save cookies', 'error')
  }
}

async function pasteCookiesClipboard() {
  let text = ''
  if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.readText) {
    try {
      text = await navigator.clipboard.readText()
    } catch (e) {}
  }
  if (text && text.trim()) {
    cookiesText.value = text.trim()
    showToast('Cookies pasted', 'success')
    return
  }
  showToast('Tap & hold text box to paste', 'info')
}

async function clearCookies() {
  const ok = await showConfirm({
    title: 'Clear Cookies',
    message: 'Are you sure you want to clear all stored cookies?',
    confirmText: 'Clear',
    isDestructive: true
  })
  if (!ok) return
  try {
    await runBridge('clear_cookies')
    cookiesText.value = ''
    cookiesActive.value = false
    cookiesLines.value = 0
    showToast('Cookies cleared', 'success')
  } catch (e) {
    showToast('Failed to clear cookies', 'error')
  }
}

async function fetchLogs() {
  try {
    const logs = await runBridge('get_logs')
    logContent.value = logs || 'No log entries recorded yet.'
    nextTick(() => {
      if (terminalCard.value) {
        terminalCard.value.scrollTop = terminalCard.value.scrollHeight
      }
    })
  } catch (e) {
    logContent.value = 'Failed to load console logs.'
  }
}

async function copyLogs() {
  if (!logContent.value || logContent.value === 'No log entries recorded yet.') {
    showToast('No logs to copy', 'info')
    return
  }
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(logContent.value)
      showToast('Logs copied to clipboard', 'success')
      return
    }
  } catch (e) {}
  showToast('Copied to clipboard', 'success')
}

async function clearLogs() {
  const ok = await showConfirm({
    title: 'Clear Activity Logs',
    message: 'Are you sure you want to clear all activity logs?',
    confirmText: 'Clear',
    isDestructive: true
  })
  if (!ok) return
  try {
    await runBridge('clear_logs')
    logContent.value = 'No log entries recorded yet.'
    showToast('Logs cleared', 'success')
  } catch (e) {
    showToast('Failed to clear logs', 'error')
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

async function checkActiveTask() {
  try {
    const raw = await runBridge('status')
    if (raw && raw !== 'binary_not_found') {
      let parsed = null
      try {
        parsed = JSON.parse(raw)
      } catch (e) {}

      if (parsed && typeof parsed === 'object') {
        if (parsed.status === 'downloading' || parsed.status === 'resolving') {
          task.value = { ...task.value, ...parsed }
          if (parsed.url && !url.value) url.value = parsed.url
          isProcessing.value = true
          startPolling()
          saveActiveTaskToStorage(task.value)
          return
        } else if (parsed.status === 'paused') {
          task.value = { ...task.value, ...parsed }
          if (parsed.url && !url.value) url.value = parsed.url
          isProcessing.value = false
          saveActiveTaskToStorage(task.value)
          return
        } else if (parsed.status === 'idle' || parsed.status === 'completed') {
          saveActiveTaskToStorage(null)
          return
        }
      }
    }
  } catch (e) {}

  // Fallback: check localStorage for unfinished task (reboot recovery)
  const saved = loadActiveTaskFromStorage()
  if (saved && (saved.status === 'downloading' || saved.status === 'resolving' || saved.status === 'paused')) {
    task.value = {
      ...saved,
      status: 'paused',
      error: saved.error || 'Interrupted by device restart. Tap Resume to continue.'
    }
    if (saved.url && !url.value) url.value = saved.url
    isProcessing.value = false
  }
}

onMounted(() => {
  if (typeof window !== 'undefined') {
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    window.addEventListener('focus', checkClipboardSniffer)
  }
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibilityChange)
  }
  loadSystemInfo()
  fetchHistory()
  loadCookies()
  fetchLogs()
  checkActiveTask()
  fetchStorageStats()
  checkClipboardSniffer()
  checkVaultStatus()
})

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('online', handleOnline)
    window.removeEventListener('offline', handleOffline)
    window.removeEventListener('focus', checkClipboardSniffer)
  }
  if (typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', onVisibilityChange)
  }
  if (pollTimer) clearInterval(pollTimer)
  if (toastTimer) clearTimeout(toastTimer)
})
</script>

<style scoped>
.offline-notice-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface-container-low);
  border: 1px solid var(--surface-container-high);
  border-left: 3px solid var(--error);
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
  font-size: 11px;
  color: var(--on-surface-variant);
  line-height: 1.4;
}

.platform-notice-box {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: var(--surface-container-low);
  border: 1px solid var(--surface-container-high);
  border-left: 3px solid var(--secondary);
  border-radius: 8px;
  padding: 8px 12px;
  margin-top: 10px;
  font-size: 11px;
  color: var(--on-surface-variant);
  line-height: 1.5;
}

.format-desc-hint {
  font-size: 11px;
  color: var(--on-surface-variant);
  margin-top: 6px;
  padding-left: 2px;
}

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
  font-family: inherit;
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
  font-family: inherit;
  font-variant-numeric: tabular-nums;
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

/* Resolution Picker Sheet Modal */
.sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.72);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.sheet-panel {
  width: 100%;
  max-width: 520px;
  background: var(--surface-container);
  border-top-left-radius: 20px;
  border-top-right-radius: 20px;
  border: 1px solid var(--surface-container-high);
  border-bottom: none;
  padding: 18px 16px calc(24px + var(--window-inset-bottom, 0px)) 16px;
  max-height: 75vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 -4px 32px rgba(0, 0, 0, 0.6);
  animation: sheet-up 0.18s cubic-bezier(0.2, 0, 0, 1);
}

@keyframes sheet-up {
  from {
    transform: translateY(100%);
  }
  to {
    transform: translateY(0);
  }
}

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: var(--surface-container-high);
  color: var(--on-surface-variant);
  cursor: pointer;
  transition: all 0.15s ease;
}

.icon-btn:active {
  transform: scale(0.92);
  background: var(--surface-container-highest);
}

.spin-loader {
  animation: spin 1s linear infinite;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--primary);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0 8px 0;
}

.skeleton-row {
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(90deg, var(--surface-container-low) 25%, var(--surface-container-high) 50%, var(--surface-container-low) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border: 1px solid var(--outline-variant);
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.res-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--surface-container-high);
  color: var(--primary);
  border: 1px solid var(--outline-variant);
  margin-right: 2px;
}

.fps-tag {
  font-size: 11px;
  color: var(--on-surface-variant);
  font-weight: 500;
}

.resolution-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  padding-right: 2px;
  scrollbar-width: thin;
}

.resolution-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-radius: 12px;
  background: var(--surface-container-low);
  border: 1px solid var(--outline-variant);
  color: var(--on-surface);
  cursor: pointer;
  user-select: none;
  transition: all 0.15s ease;
  width: 100%;
  text-align: left;
}

.resolution-row:hover {
  background: var(--surface-container-high);
  border-color: var(--primary);
}

.resolution-row:active {
  transform: scale(0.98);
  background: var(--surface-container-highest);
}

.res-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--on-surface);
  display: flex;
  align-items: center;
  gap: 6px;
}

.res-size {
  font-size: 12px;
  color: var(--on-surface-variant);
  font-weight: 500;
}

.probe-empty-area {
  padding: 12px 0 6px 0;
}

.progress-fill.indeterminate {
  background: linear-gradient(90deg, var(--surface-container-high) 0%, var(--primary) 50%, var(--surface-container-high) 100%);
  background-size: 200% 100%;
  animation: progress-shimmer 1.4s infinite ease-in-out;
}

@keyframes progress-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.custom-checkbox {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  user-select: none;
  margin: 0;
  position: relative;
}

.custom-checkbox input {
  position: absolute;
  opacity: 0;
  cursor: pointer;
  height: 0;
  width: 0;
}

.checkbox-box {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border: 1.5px solid var(--outline);
  background: var(--surface-container);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--on-primary);
  transition: all 0.15s ease;
}

.custom-checkbox input:checked ~ .checkbox-box {
  background: var(--primary);
  border-color: var(--primary);
  color: var(--on-primary);
}

.row-selected {
  background: rgba(255, 255, 255, 0.05);
}

.dialog-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 24px;
  touch-action: none;
}

.dialog-card {
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 20px;
  padding: 20px;
  width: 100%;
  max-width: 320px;
  box-shadow: 0 16px 32px rgba(0, 0, 0, 0.6);
  animation: dialog-pop 0.15s cubic-bezier(0.2, 0, 0, 1);
}

@keyframes dialog-pop {
  from {
    opacity: 0;
    transform: scale(0.92);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.dialog-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--on-surface);
  margin-bottom: 8px;
}

.dialog-message {
  font-size: 13px;
  color: var(--on-surface-variant);
  line-height: 1.5;
  margin-bottom: 20px;
  word-break: break-word;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.dialog-btn {
  padding: 8px 16px;
  font-size: 12px;
  min-width: 74px;
  border-radius: 10px;
}

/* Clipboard Sniffer Banner */
.clip-sniffer-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--surface-container-high);
  border: 1px solid var(--primary);
  border-radius: 12px;
  padding: 8px 12px;
  margin-top: 10px;
  animation: dialog-pop 0.18s cubic-bezier(0.2, 0, 0, 1);
}

.clip-sniffer-icon {
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.clip-sniffer-content {
  flex: 1;
  min-width: 0;
}

.clip-sniffer-title {
  font-size: 10px;
  font-weight: 600;
  color: var(--primary);
}

.clip-sniffer-url {
  font-size: 11px;
  color: var(--on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: inherit;
  margin-top: 2px;
}

.clip-sniffer-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.clip-action-btn {
  padding: 4px 8px;
  font-size: 11px;
  border-radius: 8px;
  gap: 4px;
}

.clip-dismiss-btn {
  width: 26px;
  height: 26px;
  background: transparent;
  border: none;
  color: var(--on-surface-variant);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Storage Card */
.storage-card {
  background: var(--surface-container-low);
  border: 1px solid var(--surface-container-high);
  border-radius: 14px;
  padding: 12px 14px;
  margin-top: 16px;
}

.storage-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.junk-clean-btn {
  padding: 5px 10px;
  font-size: 11px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 5px;
}

.junk-clean-btn.active {
  background: rgba(229, 153, 149, 0.15);
  color: var(--error);
  border-color: rgba(229, 153, 149, 0.4);
}

.storage-bar-track {
  width: 100%;
  height: 4px;
  background: var(--surface-container-high);
  border-radius: 2px;
  margin-top: 10px;
  overflow: hidden;
}

.storage-bar-fill.media {
  height: 100%;
  background: var(--primary);
  border-radius: 2px;
  transition: width 0.3s ease;
}

/* Recent Controls (Search & Chips) */
.recent-controls-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 10px;
}

.search-input-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface-container-low);
  border: 1px solid var(--surface-container-high);
  border-radius: 12px;
  padding: 6px 12px;
}

.search-input {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--on-surface);
  font-size: 12px;
  outline: none;
}

.btn-search-clear {
  background: transparent;
  border: none;
  color: var(--on-surface-variant);
  font-size: 12px;
  cursor: pointer;
  padding: 0 4px;
}

.filter-chips-row {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
  scrollbar-width: none;
}

.filter-chips-row::-webkit-scrollbar {
  display: none;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 20px;
  background: var(--surface-container-low);
  border: 1px solid var(--surface-container-high);
  color: var(--on-surface-variant);
  font-size: 11px;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.15s ease;
}

.filter-chip.active {
  background: var(--primary);
  color: var(--on-primary);
  border-color: var(--primary);
  font-weight: 600;
}

/* Lightbox / Preview */
.preview-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(14, 14, 14, 0.94);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9998;
  padding: 16px;
  touch-action: none;
}

.preview-card {
  background: var(--surface-container-high);
  border: 1px solid var(--outline-variant);
  border-radius: 20px;
  width: 100%;
  max-width: 480px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.7);
  animation: dialog-pop 0.15s cubic-bezier(0.2, 0, 0, 1);
  overflow: hidden;
}

.preview-top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--surface-container-low);
}

.preview-title-box {
  min-width: 0;
  flex: 1;
}

.preview-filename {
  font-size: 13px;
  font-weight: 600;
  color: var(--on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.preview-meta {
  font-size: 11px;
  color: var(--on-surface-variant);
  font-family: inherit;
  font-variant-numeric: tabular-nums;
  margin-top: 2px;
}

.preview-close-btn {
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  color: var(--on-surface-variant);
}

.preview-body {
  flex: 1;
  min-height: 220px;
  max-height: calc(90vh - 120px);
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  position: relative;
  overflow: hidden;
}

.preview-center-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  text-align: center;
}

.preview-image-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.preview-image {
  max-width: 100%;
  max-height: 60vh;
  object-fit: contain;
  display: block;
}

.preview-media-container {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
}

.preview-video {
  max-width: 100%;
  max-height: 60vh;
  border-radius: 8px;
}

.preview-audio-box {
  width: 100%;
  padding: 24px 16px;
  text-align: center;
}

.preview-nav-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 40px;
  height: 40px;
  border-radius: 20px;
  background: rgba(0, 0, 0, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.preview-nav-btn.prev {
  left: 8px;
}

.preview-nav-btn.next {
  right: 8px;
}

.preview-nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.preview-bottom-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-top: 1px solid var(--surface-container-low);
  background: var(--surface-container-high);
}

/* Cookie Health Grid */
.cookie-health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 8px;
}

.cookie-health-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  background: var(--surface-container-low);
  border: 1px solid var(--surface-container-high);
  transition: all 0.2s ease;
}

.cookie-health-item.active {
  border-color: rgba(99, 219, 142, 0.35);
  background: rgba(99, 219, 142, 0.08);
}

.cookie-health-icon {
  color: var(--on-surface-variant);
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.cookie-health-item.active .cookie-health-icon {
  color: var(--primary);
}

.cookie-health-info {
  min-width: 0;
  flex: 1;
}

.cookie-health-name {
  font-size: 11px;
  font-weight: 600;
  color: var(--on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cookie-health-desc {
  font-size: 9px;
  color: var(--on-surface-variant);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
}

.cookie-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--outline-variant);
  flex-shrink: 0;
}

.cookie-status-dot.active {
  background: #63db8e;
  box-shadow: 0 0 6px rgba(99, 219, 142, 0.6);
}
</style>
