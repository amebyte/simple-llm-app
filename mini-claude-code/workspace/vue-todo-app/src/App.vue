<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import TodoItem from './components/TodoItem.vue'
import TodoStats from './components/TodoStats.vue'
import TodoFilter from './components/TodoFilter.vue'
import TodoInput from './components/TodoInput.vue'

interface Todo {
  id: number
  text: string
  completed: boolean
}

const todos = ref<Todo[]>([])
const filter = ref<'all' | 'active' | 'completed'>('all')
const nextId = ref(1)

// 从 localStorage 恢复数据
onMounted(() => {
  const saved = localStorage.getItem('vue-todo-todos')
  if (saved) {
    const parsed = JSON.parse(saved)
    todos.value = parsed.todos
    nextId.value = parsed.nextId || 1
  }
})

// 保存到 localStorage
watch(todos, (newTodos) => {
  localStorage.setItem('vue-todo-todos', JSON.stringify({
    todos: newTodos,
    nextId: nextId.value
  }))
}, { deep: true })

// 计算属性
const filteredTodos = computed(() => {
  switch (filter.value) {
    case 'active':
      return todos.value.filter(todo => !todo.completed)
    case 'completed':
      return todos.value.filter(todo => todo.completed)
    default:
      return todos.value
  }
})

const stats = computed(() => {
  const total = todos.value.length
  const completed = todos.value.filter(todo => todo.completed).length
  const pending = total - completed
  return { total, completed, pending }
})

// 操作方法
const addTodo = (text: string) => {
  todos.value.unshift({
    id: nextId.value++,
    text,
    completed: false
  })
}

const updateTodoText = (id: number, text: string) => {
  const todo = todos.value.find(t => t.id === id)
  if (todo) {
    todo.text = text
  }
}

const updateTodoCompleted = (id: number, completed: boolean) => {
  const todo = todos.value.find(t => t.id === id)
  if (todo) {
    todo.completed = completed
  }
}

const deleteTodo = (id: number) => {
  const index = todos.value.findIndex(t => t.id === id)
  if (index !== -1) {
    todos.value.splice(index, 1)
  }
}

const clearCompleted = () => {
  todos.value = todos.value.filter(todo => !todo.completed)
}
</script>

<template>
  <div class="app">
    <header class="header">
      <h1 class="title">📝 Todo List</h1>
      <p class="subtitle">简洁高效的任务管理工具</p>
    </header>

    <main class="main">
      <div class="container">
        <TodoStats
          :total="stats.total"
          :completed="stats.completed"
          :pending="stats.pending"
        />

        <TodoInput @add="addTodo" />

        <TodoFilter v-model:filter="filter" />

        <div class="todo-list-container">
          <TransitionGroup name="todo-list" tag="div" class="todo-list">
            <TodoItem
              v-for="todo in filteredTodos"
              :key="todo.id"
              :todo="todo"
              @update:text="updateTodoText"
              @update:completed="updateTodoCompleted"
              @delete="deleteTodo"
            />
          </TransitionGroup>

          <div v-if="filteredTodos.length === 0" class="empty-state">
            <div class="empty-icon">📋</div>
            <p class="empty-text">
              {{ filter === 'all' ? '还没有任务，添加一个吧！' : 
                 filter === 'active' ? '没有进行中的任务' : 
                 '没有已完成的任务' }}
            </p>
          </div>
        </div>

        <div class="actions">
          <button 
            v-if="stats.completed > 0" 
            @click="clearCompleted" 
            class="clear-btn"
          >
            清除已完成 ({{ stats.completed }})
          </button>
        </div>
      </div>
    </main>

    <footer class="footer">
      <p>双击任务进行编辑 • 使用 localStorage 自动保存</p>
    </footer>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.header {
  text-align: center;
  margin-bottom: 40px;
  color: white;
}

.title {
  font-size: 48px;
  font-weight: bold;
  margin-bottom: 8px;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.subtitle {
  font-size: 18px;
  opacity: 0.9;
}

.main {
  max-width: 600px;
  margin: 0 auto;
}

.container {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
  border-radius: 20px;
  padding: 32px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.todo-list-container {
  min-height: 200px;
}

.todo-list {
  margin-bottom: 20px;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: rgba(255, 255, 255, 0.8);
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-text {
  font-size: 18px;
}

.actions {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}

.clear-btn {
  background: rgba(239, 68, 68, 0.2);
  color: white;
  border: 1px solid rgba(239, 68, 68, 0.4);
  padding: 12px 24px;
  border-radius: 12px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.clear-btn:hover {
  background: rgba(239, 68, 68, 0.3);
  transform: translateY(-2px);
}

.footer {
  text-align: center;
  margin-top: 40px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
}

/* 动画效果 */
.todo-list-move,
.todo-list-enter-active,
.todo-list-leave-active {
  transition: all 0.5s ease;
}

.todo-list-enter-from {
  opacity: 0;
  transform: translateX(-30px);
}

.todo-list-leave-to {
  opacity: 0;
  transform: translateX(30px);
}

.todo-list-leave-active {
  position: absolute;
}
</style>