<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { api } from '../api'
import Icon from '../components/Icon.vue'

const store = useAppStore()
const router = useRouter()

const sources = ref([])
const loading = ref(false)
const editing = ref(null)   // 正在编辑的 source 副本，null=未编辑
const form = ref({ name: '', url: '', enabled: true })
const showAdd = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await api.adminListSources()
    if (res.code === 0) sources.value = res.data
  } catch (err) {
    alert('加载失败：' + err.message)
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function addSource() {
  if (!form.value.url.trim()) { alert('请填写解析源 URL'); return }
  try {
    const res = await api.adminAddSource(form.value.name, form.value.url, form.value.enabled)
    if (res.code === 0) {
      form.value = { name: '', url: '', enabled: true }
      showAdd.value = false
      await load()
    }
  } catch (err) {
    alert('新增失败：' + err.message)
  }
}

function startEdit(s) {
  editing.value = { ...s }
}

async function saveEdit() {
  try {
    const res = await api.adminUpdateSource(editing.value.id, {
      name: editing.value.name,
      url: editing.value.url,
    })
    if (res.code === 0) { editing.value = null; await load() }
  } catch (err) {
    alert('保存失败：' + err.message)
  }
}

async function toggleEnabled(s) {
  try {
    await api.adminUpdateSource(s.id, { enabled: !s.enabled })
    await load()
  } catch (err) {
    alert('操作失败：' + err.message)
  }
}

async function remove(s) {
  if (!confirm(`确定删除解析源「${s.name}」？`)) return
  try {
    await api.adminDeleteSource(s.id)
    await load()
  } catch (err) {
    alert('删除失败：' + err.message)
  }
}

function logout() {
  store.logout()
  router.push('/')
}
</script>

<template>
  <main class="admin-wrap">
    <div class="admin-head">
      <div>
        <h1>VIP 解析源管理</h1>
        <p>管理员 {{ store.user?.username }} · 共 {{ sources.length }} 个源</p>
      </div>
      <div class="head-actions">
        <button class="btn-primary" @click="showAdd = !showAdd">
          <Icon name="bolt" :size="16" /> 新增源
        </button>
        <button class="btn-secondary" @click="router.push('/')">
          <Icon name="external" :size="15" /> 首页
        </button>
        <button class="btn-secondary" @click="logout">退出</button>
      </div>
    </div>

    <transition name="slide">
      <div v-if="showAdd" class="add-form card">
        <div class="add-row">
          <label class="af-name">
            <span>名称</span>
            <input v-model="form.name" placeholder="如：虾米解析" />
          </label>
          <label class="af-url">
            <span>解析源 URL（以 ?url= 结尾）</span>
            <input v-model="form.url" placeholder="https://jx.example.com/?url=" />
          </label>
        </div>
        <div class="add-actions">
          <label class="enable-toggle">
            <input type="checkbox" v-model="form.enabled" /> 启用
          </label>
          <button class="btn-primary" @click="addSource"><Icon name="check" :size="15" /> 添加</button>
          <button class="btn-secondary" @click="showAdd = false">取消</button>
        </div>
      </div>
    </transition>

    <div class="source-table card">
      <div v-if="loading" class="table-empty">加载中…</div>
      <div v-else-if="sources.length === 0" class="table-empty">暂无解析源</div>
      <table v-else>
        <thead>
          <tr>
            <th class="c-status">状态</th>
            <th class="c-name">名称</th>
            <th class="c-url">解析源 URL</th>
            <th class="c-ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in sources" :key="s.id" :class="{ disabled: !s.enabled }">
            <td class="c-status">
              <button class="toggle" :class="{ on: s.enabled }" @click="toggleEnabled(s)" :title="s.enabled ? '点击禁用' : '点击启用'">
                <span class="knob"></span>
              </button>
            </td>
            <td class="c-name">
              <template v-if="editing && editing.id === s.id">
                <input v-model="editing.name" class="edit-input" />
              </template>
              <span v-else>{{ s.name }}</span>
            </td>
            <td class="c-url">
              <template v-if="editing && editing.id === s.id">
                <input v-model="editing.url" class="edit-input mono" />
              </template>
              <code v-else>{{ s.url }}</code>
            </td>
            <td class="c-ops">
              <template v-if="editing && editing.id === s.id">
                <button class="op save" @click="saveEdit" title="保存"><Icon name="check" :size="15" /></button>
                <button class="op" @click="editing = null" title="取消"><Icon name="close" :size="15" /></button>
              </template>
              <template v-else>
                <button class="op" @click="startEdit(s)" title="编辑"><Icon name="refresh" :size="15" /></button>
                <button class="op danger" @click="remove(s)" title="删除"><Icon name="trash" :size="15" /></button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </main>
</template>

<style scoped>
.admin-wrap {
  flex: 1;
  width: 100%;
  max-width: 1080px;
  margin: 0 auto;
  padding: 32px 24px 64px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.admin-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.admin-head h1 { font-size: 24px; font-weight: 800; letter-spacing: -0.02em; margin: 0; }
.admin-head p { font-size: 13px; color: var(--text-tertiary); margin: 4px 0 0; }
.head-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.add-form { display: flex; flex-direction: column; gap: 14px; }
.add-row { display: flex; gap: 14px; flex-wrap: wrap; }
.af-name { flex: 1; min-width: 160px; display: flex; flex-direction: column; gap: 6px; }
.af-url { flex: 2.5; min-width: 240px; display: flex; flex-direction: column; gap: 6px; }
.add-row span { font-size: 12px; font-weight: 600; color: var(--text-secondary); }
.add-actions { display: flex; align-items: center; gap: 12px; }
.enable-toggle { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-secondary); margin-right: auto; }

.source-table { padding: 0; overflow: hidden; }
.table-empty { padding: 48px; text-align: center; color: var(--text-tertiary); }

table { width: 100%; border-collapse: collapse; }
thead th {
  text-align: left;
  padding: 14px 16px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  border-bottom: 1px solid var(--border);
  background: var(--bg-subtle);
}
tbody td { padding: 12px 16px; border-bottom: 1px solid var(--border); font-size: 14px; vertical-align: middle; }
tbody tr:last-child td { border-bottom: none; }
tbody tr.disabled { opacity: 0.5; }
tbody tr:hover { background: var(--bg-hover); }

.c-status { width: 64px; }
.c-name { width: 160px; font-weight: 600; }
.c-ops { width: 110px; text-align: right; }
.c-url code {
  font-family: var(--font-mono);
  font-size: 12.5px;
  color: var(--text-secondary);
  word-break: break-all;
}

.edit-input {
  width: 100%;
  padding: 6px 10px;
  font-size: 13px;
}
.edit-input.mono { font-family: var(--font-mono); }

.toggle {
  width: 40px;
  height: 22px;
  border-radius: var(--radius-pill);
  background: var(--border-strong);
  position: relative;
  transition: background var(--dur) var(--ease);
}
.toggle.on { background: var(--accent); }
.knob {
  position: absolute;
  top: 2px; left: 2px;
  width: 18px; height: 18px;
  border-radius: 50%;
  background: #fff;
  box-shadow: var(--shadow-xs);
  transition: transform var(--dur) var(--ease-spring);
}
.toggle.on .knob { transform: translateX(18px); }

.op {
  width: 32px; height: 32px;
  border-radius: var(--radius-xs);
  background: transparent;
  color: var(--text-tertiary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.op:hover { background: var(--accent-soft); color: var(--accent); }
.op.danger:hover { background: var(--danger-soft); color: var(--danger); }
.op.save:hover { background: var(--accent-soft); color: var(--accent); }

.slide-enter-active, .slide-leave-active { transition: all 0.3s var(--ease-out); }
.slide-enter-from, .slide-leave-to { opacity: 0; transform: translateY(-12px); }

@media (max-width: 768px) {
  .c-url { display: none; }
  .admin-wrap { padding: 20px 16px 48px; }
}
</style>
