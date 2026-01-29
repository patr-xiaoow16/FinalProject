<template>
  <transition name="fade">
    <div v-if="message.text" :class="['message-toast', message.type]">{{ message.text }}</div>
  </transition>
</template>

<script>
export default {
  name: 'MessageToast',
  props: {
    message: {
      type: Object,
      default: () => ({ text: '', type: 'info' })
    }
  }
}
</script>


