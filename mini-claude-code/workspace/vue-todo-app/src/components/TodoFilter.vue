<script setup lang="ts">
interface Props {
  filter: 'all' | 'active' | 'completed'
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:filter': [filter: 'all' | 'active' | 'completed']
}>()

const filters = [
  { value: 'all', label: '全部' },
  { value: 'active', label: '进行中' },
  { value: 'completed', label: '已完成' }
]
</script>

<template>
  <div class="filter-container">
    <div class="filter-buttons">
      <button
        v-for="f in filters"
        :key="f.value"
        @click="emit('update:filter', f.value)"
        :class="['filter-btn', { active: filter === f.value }]"
      >
        {{ f.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.filter-container {
  margin-bottom: 24px;
}

.filter-buttons {
  display: flex;
  gap: 8px;
  background: rgba(255, 255, 255, 0.95);
  padding: 8px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.filter-btn {
  flex: 1;
  padding: 12px 16px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #6b7280;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s ease;
}

.filter-btn:hover {
  background: rgba(79, 70, 229, 0.1);
  color: #4f46e5;
}

.filter-btn.active {
  background: #4f46e5;
  color: white;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3);
}
</style>