<template>
  <div class="cli-releases">
    <div v-if="loading" class="loading">Loading releases…</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else>
      <div v-for="release in releases" :key="release.tag_name" class="release-block">
        <div class="release-header">
          <span class="release-tag">{{ release.tag_name }}</span>
          <span class="release-date">{{ formatDate(release.published_at) }}</span>
          <a :href="release.html_url" target="_blank" rel="noopener" class="release-link">GitHub</a>
        </div>

        <div class="platform-grid">
          <a
            v-for="asset in groupedAssets(release.assets)"
            :key="asset.name"
            :href="asset.browser_download_url"
            class="download-card"
          >
            <span class="platform-icon">{{ asset.icon }}</span>
            <span class="platform-label">{{ asset.label }}</span>
            <span class="platform-arch">{{ asset.arch }}</span>
            <span class="download-count">{{ asset.download_count.toLocaleString() }} downloads</span>
          </a>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface Asset {
  name: string
  browser_download_url: string
  download_count: number
  size: number
}

interface Release {
  tag_name: string
  name: string
  html_url: string
  published_at: string
  assets: Asset[]
}

interface DisplayAsset extends Asset {
  icon: string
  label: string
  arch: string
}

const releases = ref<Release[]>([])
const loading = ref(true)
const error = ref('')

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', { year: 'numeric', month: 'short', day: 'numeric' })
}

function groupedAssets(assets: Asset[]): DisplayAsset[] {
  return assets.map(a => {
    let icon = '📦', label = 'Unknown', arch = ''
    const n = a.name.toLowerCase()
    if (n.includes('android')) {
      icon = '🤖'; label = 'Android'
      if (n.includes('arm64')) arch = 'arm64'
      else if (n.includes('arm32')) arch = 'arm32'
      else if (n.includes('x86_64')) arch = 'x86_64'
    } else if (n.includes('linux')) {
      icon = '🐧'; label = 'Linux'
      if (n.includes('x64')) arch = 'x64'
      else if (n.includes('arm64')) arch = 'arm64'
    } else if (n.includes('windows')) {
      icon = '🪟'; label = 'Windows'
      if (n.includes('x64')) arch = 'x64'
    } else if (n.includes('macos') || n.includes('darwin')) {
      icon = '🍎'; label = 'macOS'
      if (n.includes('arm64')) arch = 'arm64'
      else if (n.includes('x64')) arch = 'x64'
    }
    return { ...a, icon, label, arch }
  }).sort((a, b) => a.label.localeCompare(b.label) || a.arch.localeCompare(b.arch))
}

onMounted(async () => {
  try {
    const res = await fetch('https://api.github.com/repos/MichTronics/MeshCoreNG-cli-app/releases')
    if (!res.ok) throw new Error(`GitHub API returned ${res.status}`)
    releases.value = await res.json()
  } catch (e: any) {
    error.value = `Could not load releases: ${e.message}`
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.cli-releases {
  margin: 1.5rem 0;
}

.loading, .error {
  padding: 1rem;
  color: var(--vp-c-text-2);
  font-style: italic;
}

.error {
  color: var(--vp-c-danger-1);
}

.release-block {
  margin-bottom: 2.5rem;
}

.release-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.release-tag {
  font-family: var(--vp-font-family-mono);
  font-weight: 600;
  font-size: 1.1rem;
  color: var(--vp-c-brand-1);
}

.release-date {
  color: var(--vp-c-text-2);
  font-size: 0.875rem;
}

.release-link {
  margin-left: auto;
  font-size: 0.875rem;
  color: var(--vp-c-brand-1);
  text-decoration: none;
}

.release-link:hover {
  text-decoration: underline;
}

.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.75rem;
}

.download-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 1rem 0.75rem;
  border: 1px solid var(--vp-c-divider);
  border-radius: 8px;
  text-decoration: none;
  color: var(--vp-c-text-1);
  transition: border-color 0.2s, background 0.2s;
  cursor: pointer;
}

.download-card:hover {
  border-color: var(--vp-c-brand-1);
  background: var(--vp-c-brand-soft);
}

.platform-icon {
  font-size: 1.75rem;
  line-height: 1;
}

.platform-label {
  font-weight: 600;
  font-size: 0.95rem;
}

.platform-arch {
  font-family: var(--vp-font-family-mono);
  font-size: 0.8rem;
  color: var(--vp-c-text-2);
}

.download-count {
  font-size: 0.75rem;
  color: var(--vp-c-text-3);
  margin-top: 0.125rem;
}
</style>
