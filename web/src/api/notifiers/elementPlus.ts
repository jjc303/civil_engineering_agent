import { ElMessage } from 'element-plus'
import { registerApiNotifier, type ApiNotifier } from '../ports'

export function createElementPlusApiNotifier(): ApiNotifier {
  return {
    error: (message) => ElMessage.error(message),
    warning: (message) => ElMessage.warning(message),
  }
}

export function registerElementApiNotifier(): void {
  registerApiNotifier(createElementPlusApiNotifier())
}
