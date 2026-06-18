import { ref } from 'vue'

const toastState = ref({
  visible: false,
  message: '',
  type: 'info',
  duration: 3000
})

let timer = null

export function useToast() {
  const show = (message, type = 'info', duration = 3000) => {
    clearTimeout(timer)
    toastState.value = {
      visible: true,
      message,
      type,
      duration
    }
    if (duration > 0) {
      timer = setTimeout(() => {
        toastState.value.visible = false
      }, duration)
    }
  }

  const success = (message, duration) => show(message, 'success', duration)
  const error = (message, duration) => show(message, 'error', duration)
  const warning = (message, duration) => show(message, 'warning', duration)
  const info = (message, duration) => show(message, 'info', duration)

  const hide = () => {
    clearTimeout(timer)
    toastState.value.visible = false
  }

  return {
    toastState,
    show,
    success,
    error,
    warning,
    info,
    hide
  }
}
