import { ElMessage, ElMessageBox } from 'element-plus'
import { registerApiNotifier, registerConfirmDialog, type ApiNotifier } from '../ports'

export function createElementPlusApiNotifier(): ApiNotifier {
  return {
    error: (message) => ElMessage.error(message),
    warning: (message) => ElMessage.warning(message),
    success: (message) => ElMessage.success(message),
  }
}

export function registerElementApiNotifier(): void {
  registerApiNotifier(createElementPlusApiNotifier())
  registerConfirmDialog(async ({ title, message, confirmText, cancelText }) => {
    try {
      await ElMessageBox.confirm(message, title, {
        confirmButtonText: confirmText,
        cancelButtonText: cancelText,
        type: 'warning',
      })
      return true
    } catch {
      return false
    }
  })
}
