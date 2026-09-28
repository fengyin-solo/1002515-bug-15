<template>
  <section class="page" data-module="cable">
    <header class="page-head">
      <div>
        <h2>信号电缆管理</h2>
        <p class="page-desc">维护信号电缆，围绕电缆编号、起止站点、电缆芯数、绝缘电阻做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="triggerImport">导入台账表格</button>
        <button class="btn" type="button" @click="exportRows">导出信号电缆清单</button>
        <input
          ref="fileInput"
          type="file"
          accept=".csv,text/csv"
          hidden
          @change="onFilePicked"
        />
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>电缆编号</span>
        <input v-model="keyword" placeholder="按电缆编号检索" />
      </label>
      <label class="filter-item">
        <span>电缆状态</span>
        <select v-model="status">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <button v-if="column === '电缆编号'" class="link" type="button" @click="openDetail(row)">
              {{ row[column] ?? '—' }}
            </button>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无信号电缆数据，可先导入台账或登记信号电缆</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条信号电缆记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
    </footer>

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal-card">
        <header class="modal-head">
          <h3>信号电缆明细</h3>
          <button class="btn ghost" type="button" @click="detail = null">关闭</button>
        </header>
        <dl class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detail[column] ?? '—' }}</dd>
          </template>
        </dl>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/cable'
const columns = ["电缆编号", "起止站点", "电缆芯数", "绝缘电阻", "对地电压", "敷设方式", "接头数量", "电缆状态"]
const actions = ["登记报警", "查找接地点", "办理更换"]
const statuses = ["绝缘良好", "绝缘下降", "接地报警", "已更换"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const keyword = ref('')
const status = ref('')
const detail = ref<Row | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const stats = ref([
  { label: '良好电缆', value: 0, status: '绝缘良好' },
  { label: '绝缘下降电缆', value: 0, status: '绝缘下降' },
  { label: '接地报警电缆', value: 0, status: '接地报警' },
])

function buildQuery(extra: Record<string, string> = {}) {
  const params = new URLSearchParams()
  if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
  if (status.value) params.set('status', status.value)
  for (const [key, value] of Object.entries(extra)) params.set(key, value)
  const query = params.toString()
  return query ? `?${query}` : ''
}

function resetFilters() {
  keyword.value = ''
  status.value = ''
  void reload()
}

function exportRows() {
  // 导出与列表共用筛选口径：带上当前 keyword/status，由后端返回 CSV 下载
  window.open(`${ENDPOINT}/export${buildQuery()}`, '_blank')
}

function triggerImport() {
  errorMessage.value = ''
  noticeMessage.value = ''
  fileInput.value?.click()
}

async function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  // 允许重复选择同一个文件：否则修正后重传不会触发 change
  input.value = ''
  if (!file) return
  errorMessage.value = ''
  noticeMessage.value = '正在导入台账，请勿关闭页面……'
  try {
    const response = await request(`${ENDPOINT}/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'text/csv; charset=utf-8' },
      body: file,
    })
    if (!response.ok) {
      throw new Error(`导入请求失败（HTTP ${response.status}），整批数据未写入`)
    }
    const payload = await response.json()
    if (!payload.ok) {
      throw new Error(payload.message || '表头或内容校验未通过，整批退回')
    }
    noticeMessage.value = payload.message || '导入完成'
    await reload()
  } catch (error) {
    noticeMessage.value = ''
    errorMessage.value = error instanceof Error ? error.message : '信号电缆台账导入失败'
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('信号电缆明细读取失败')
    }
    detail.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '信号电缆明细读取失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    if (!response.ok) {
      throw new Error('信号电缆动作未生效，请稍后重试')
    }
    const payload = await response.json()
    if (!payload.ok) {
      throw new Error(payload.message || '信号电缆动作未生效')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '信号电缆操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const [listResponse, ...countResponses] = await Promise.all([
      request(`${ENDPOINT}${buildQuery({ page: '1', size: '200' })}`),
      ...stats.value.map((item) =>
        request(`${ENDPOINT}?status=${encodeURIComponent(item.status)}&page=1&size=1`),
      ),
    ])
    if (!listResponse.ok || countResponses.some((item) => !item.ok)) {
      throw new Error('信号电缆列表读取失败')
    }
    const payload = await listResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await Promise.all(
      countResponses.map(async (response, index) => {
        const data = await response.json()
        stats.value[index].value = data.total ?? 0
      }),
    )
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '信号电缆列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.page-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.filter-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}
.filter-item input,
.filter-item select {
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  min-width: 160px;
}
.notice-text {
  color: #176b3a;
}
.row-actions {
  white-space: nowrap;
}
.row-actions .link + .link {
  margin-left: 10px;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal-card {
  background: #fff;
  border-radius: 8px;
  width: min(640px, 92vw);
  max-height: 82vh;
  overflow: auto;
  padding: 16px 20px;
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 6px 12px;
  margin: 0;
}
.detail-grid dt {
  color: var(--muted);
  font-size: 13px;
}
.detail-grid dd {
  margin: 0;
  font-size: 13px;
}
</style>
