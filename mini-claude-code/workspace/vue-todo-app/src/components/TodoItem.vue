<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  todo: {
    id: number
    text: string
    completed: boolean
  }
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:completed': [id: number, completed: boolean]
  'delete': [id: number]
  'update:text': [id: number, text: string]
}>()

const isEditing = ref(false)
const editText = ref('')

const startEditing = () => {
  isEditing.value = true
  editText.value = props.todo.text
}

const saveEdit = () => {
  if (editText.value.trim()) {
    emit('update:text', props.todo.id, editText.value.trim())
  }
  isEditing.value = false
}

const cancelEdit = () => {
  isEditing.value = false
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter') {
    saveEdit()
  } else if (e.key === 'Escape') {
    cancelEdit()
  }
}
</script>

<template>
  <div class="todo-item" :class="{ completed: todo.completed }">
    <div class="todo-content">
      <input
        type="checkbox"
        :checked="todo.completed"
        @change="emit('update:completed', todo.id, !todo.completed)"
        class="todo-checkbox"
      />
      
      <div v-if="!isEditing" class="todo-text" @dblclick="startEditing">
        <span>{{ todo.text }}</span>
      </div>
      
      <input
        v-else
        v-model="editText"
        @blur="saveEdit"
        @keydown="handleKeydown"
        class="todo-edit-input"
        type="text"
        ref="editInput"
        @focus="e => e.target.select()"
      />
    </div>
    
    <button @click="emit('delete', todo.id)" class="delete-btn">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.todo-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  margin-bottom: 8px;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  border-left: 4px solid #4f46e5;
}

.todo-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.todo-item.completed {
  opacity: 0.7;
  border-left-color: #10b981;
}

.todo-content {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.todo-checkbox {
  width: 20px;
  height: 20px;
  cursor: pointer;
  accent-color: #4f46e5;
}

.todo-text {
  flex: 1;
  cursor: pointer;
  padding: 4px 0;
  transition: color 0.2s;
}

.todo-text:hover {
  color: #4f46e5;
}

.todo-item.completed .todo-text {
  text-decoration: line-through;
  color: #6b7280;
}

.todo-edit-input {
  flex: 1;
  padding: 8px 12px;
  border: 2px solid #4f46e5;
  border-radius: 8px;
  font-size: 16px;
  outline: none;
  transition: border-color 0.2s;
}

.todo-edit-input:focus {
  border-color: #7c3aed;
}

.delete-btn {
  background: rgba(239, 68, 68, 0.1);
  border: none;
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  color: #ef4444;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.delete-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  transform: scale(1.05);
}
</style>