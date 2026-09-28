<template>
  <section class="page" data-module="cable">
    <header class="page-head">
      <div>
        <h2>信号电缆管理</h2>
        <p class="page-desc">维护信号电缆，围绕电缆编号、起止站点、电缆芯数、绝缘电阻做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="triggerImport">导入电缆台账</button>
        <button class="btn primary" type="button" @click="exportRows">导出信号电缆清单</button>
        <input
          ref="fileInput"
          type="file"
          accept=".csv,text/csv"
          class="hidden-file"
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
        <input v-model="filters.keyword" placeholder="按电缆编号检索" />
      </label>
      <label class="filter-item">
        <span>电缆状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <p class="hint-text">
      导入模板列顺序（须逐列一致，否则整批退回）：{{ columns.join('、') }}；空值行将整行跳过。
    </p>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">查看详情</button>
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
          <td :colspan="columns.length + 1" class="empty-state">暂无信号电缆数据，可先导入电缆台账</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条信号电缆记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="successMessage" class="success-text">{{ successMessage }}</span>
    </footer>

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal-card">
        <header class="modal-head">
          <h3>电缆详情 · {{ detail['电缆编号'] }}</h3>
          <button class="link" type="button" @click="detail = null">关闭</button>
        </header>
        <dl class="detail-list">
          <div v-for="column in columns" :key="column" class="detail-row">
            <dt>{{ column }}</dt>
            <dd>{{ detail[column] ?? '—' }}</dd>
          </div>
        </dl>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/cable'
const columns = ["电缆编号", "起止站点", "电缆芯数", "绝缘电阻", "对地电压", "敷设方式", "接头数量", "电缆状态"]
const actions = ["登记报警", "查找接地点", "办理更换"]
const statuses = ["绝缘良好", "绝缘下降", "接地报警", "已更换"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const successMessage = ref('')
const detail = ref<Row | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const filters = ref<{ keyword: string; status: string }>({ keyword: '', status: ''})

const stats = computed(() => [
  { label: '良好电缆', value: countByStatus('绝缘良好') },
  { label: '绝缘下降电缆', value: countByStatus('绝缘下降') },
  { label: '接地报警电缆', value: countByStatus('接地报警') },
])

function countByStatus(status: string): number {
  return rows.value.filter((row) => row['电缆状态'] === status).length
}

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  void reload()
}

function buildQuery(withFilters = true): string {
  const params = new URLSearchParams()
  if (withFilters) {
    if (filters.value.keyword.trim()) params.set('keyword', filters.value.keyword.trim())
    if (filters.value.status) params.set('status', filters.value.status)
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}

async function exportRows() {
  errorMessage.value = ''
  try {
    // 与列表同口径：带当前筛选条件（含电缆状态）下载 CSV。
    const response = await request(`${ENDPOINT}/export${buildQuery()}`)
    if (!response.ok) {
      throw new Error('信号电缆清单导出失败')
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '信号电缆台账.csv'
    link.click()
    URL.revokeObjectURL(url)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '信号电缆清单导出失败'
  }
}

function triggerImport() {
  errorMessage.value = ''
  successMessage.value = ''
  fileInput.value?.click()
}

async function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) {
    return
  }
  errorMessage.value = ''
  successMessage.value = ''
  try {
    // 以原始 CSV 文本提交；后端先整批校验再一次性提交，中途失败也不会留下半份数据。
    const response = await request(`${ENDPOINT}/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'text/csv; charset=utf-8' },
      body: file,
    })
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload?.detail ?? '台账导入失败，整批未写入')
    }
    const skipped = (payload.skipped_rows ?? []) as number[]
    const parts = [
      `导入完成：新增 ${payload.created ?? 0} 条`,
      `更新 ${payload.updated ?? 0} 条（按电缆编号合并）`,
    ]
    parts.push(skipped.length ? `跳过 ${skipped.length} 行，行号：${skipped.join('、')}` : '无跳过行')
    successMessage.value = parts.join('，')
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '台账导入失败，整批未写入'
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    // 详情始终取后端单条明细，保证与列表的电缆状态来自同一份数据。
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('电缆详情读取失败')
    }
    detail.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '电缆详情读取失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    if (!response.ok) {
      throw new Error('信号电缆动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '信号电缆操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}${buildQuery()}`)
    if (!response.ok) {
      throw new Error('信号电缆列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '信号电缆列表读取失败'
  }
}

onMounted(reload)
</script>
