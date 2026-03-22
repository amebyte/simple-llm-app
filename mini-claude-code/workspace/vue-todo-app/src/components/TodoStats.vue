<script setup lang="ts">
interface Props {
  total: number
  completed: number
  pending: number
}

defineProps<Props>()
</script>

<template>
  <div class="stats-container">
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-value">{{ total }}</div>
        <div class="stat-label">总任务</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-value">{{ pending }}</div>
        <div class="stat-label">进行中</div>
      </div>
      
      <div class="stat-card">
        <div class="stat-value">{{ completed }}</div>
        <div class="stat-label">已完成</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats-container {
  margin-bottom: 24px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.stat-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transition: transform 0.3s ease;
  border-top: 4px solid;
}

.stat-card:hover {
  transform: translateY(-4px);
}

.stat-card:nth-child(1) {
  border-top-color: #4f46e5;
}

.stat-card:nth-child(2) {
  border-top-color: #f59e0b;
}

.stat-card:nth-child(3) {
  border-top-color: #10b981;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  margin-bottom: 8px;
}

.stat-card:nth-child(1) .stat-value {
  color: #4f46e5;
}

.stat-card:nth-child(2) .stat-value {
  color: #f59e0b;
}

.stat-card:nth-child(3) .stat-value {
  color: #10b981;
}

.stat-label {
  font-size: 14px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 1px;
}
</style>