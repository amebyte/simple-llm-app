<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  'add': [text: string]
}>()

const newTodoText = ref('')

const addTodo = () => {
  const text = newTodoText.value.trim()
  if (text) {
    emit('add', text)
    newTodoText.value = ''
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter') {
    addTodo()
  }
}
</script>

<template>
  <div class="input-container">
    <div class="input-wrapper">
      <input
        v-model="newTodoText"
        @keydown="handleKeydown"
        placeholder="添加新任务..."
        class="todo-input"
        type="text"
      />
      <button @click="addTodo" class="add-btn">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 5v14M5 12h14" />
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.input-container {
  margin-bottom: 24px;
}

.input-wrapper {
  position: relative;
  display: flex;
  gap: 12px;
}

.todo-input {
  flex: 1;
  padding: 16px 20px;
  border: 2px solid rgba(79, 70, 229, 0.2);
  border-radius: 12px;
  font-size: 16px;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transition: all 0.3s ease;
  outline: none;
}

.todo-input:focus {
  border-color: #4f46e5;
  box-shadow: 0 4px 16px rgba(79, 70, 229, 0.2);
}

.todo-input::placeholder {
  color: #9ca3af;
}

.add-btn {
  padding: 16px 24px;
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
  border: none;
  border-radius: 12px;
  color: white;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
}

.add-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.4);
}

.add-btn:active {
  transform: translateY(0);
}
</style>