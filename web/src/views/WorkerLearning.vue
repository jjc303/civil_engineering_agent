<template>
  <main class="worker-page"><article class="paper" v-if="task"><div class="brand">施工安全 · 学习任务</div><h1>{{ task.title }}</h1><section><h2>学习材料</h2><p class="material">{{ task.material }}</p></section>
    <section v-if="!result"><h2>答题</h2><div v-for="(question, index) in task.questions" :key="index" class="question"><strong>{{ index + 1 }}. {{ question.stem }}</strong><label v-for="(option, optionIndex) in question.options" :key="optionIndex"><input v-model="answers[index]" type="radio" :name="`q${index}`" :value="optionIndex" />{{ String.fromCharCode(65 + optionIndex) }}. {{ option }}</label></div>
      <h2>确认身份并提交</h2><div class="identity"><label>工号<input v-model.trim="workerId" autocomplete="off" placeholder="请输入工号" /></label><label>姓名<input v-model.trim="workerName" autocomplete="name" placeholder="请输入姓名" /></label></div><p class="hint">每个工号在本任务中只能提交一次，请核对后再提交。</p><button class="submit" :disabled="busy" @click="submit">{{ busy ? '提交中…' : '提交答案' }}</button></section>
    <section v-else class="result"><h2>提交成功</h2><p>成绩：<strong>{{ result.score }} 分</strong></p><p>{{ result.passed ? '已达到及格线' : '未达到及格线' }}</p></section>
  </article><article v-else class="paper"><h1>{{ error || '正在加载学习任务…' }}</h1></article></main>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getPublicTraining, submitTraining } from '@/api/learning'
const route = useRoute(), token = String(route.params.token || '')
const task = ref<Awaited<ReturnType<typeof getPublicTraining>> | null>(null), answers = ref<number[]>([])
const workerId = ref(''), workerName = ref(''), busy = ref(false), error = ref('')
const result = ref<{ score: number; passed: boolean } | null>(null)
onMounted(async () => { try { task.value = await getPublicTraining(token); answers.value = task.value.questions.map(() => -1) } catch { error.value = '学习任务不存在或已失效' } })
async function submit() { if (!workerId.value || !workerName.value) return ElMessage.warning('请填写工号和姓名'); if (answers.value.some(x => x < 0)) return ElMessage.warning('请完成全部题目'); busy.value = true; try { result.value = await submitTraining(token, { worker_id: workerId.value, worker_name: workerName.value, answers: answers.value }) } catch { ElMessage.error('提交失败，请核对工号或联系管理员') } finally { busy.value = false } }
</script>
<style scoped>
.worker-page{min-height:100dvh;background:#eef2f7;padding:24px 12px;color:#263244}.paper{max-width:680px;margin:auto;background:white;border-radius:20px;padding:30px;box-shadow:0 8px 35px #253b5314}.brand{color:#5876b1;font-weight:700;letter-spacing:.08em}.paper h1{font-size:26px}.paper h2{font-size:19px;margin-top:30px}.material{white-space:pre-wrap;line-height:1.85}.question{padding:16px 0;border-bottom:1px solid #e5eaf0}.question label{display:block;padding:11px 7px;line-height:1.5}.question input{margin-right:10px;accent-color:#3869d4}.identity{display:grid;grid-template-columns:1fr 1fr;gap:12px}.identity label{display:grid;gap:7px}.identity input{font:inherit;padding:11px;border:1px solid #c9d3e2;border-radius:9px;min-width:0}.hint{color:#7e8a9b;font-size:13px}.submit{width:100%;border:0;background:#3869d4;color:white;padding:14px;border-radius:10px;font:inherit;font-weight:700}.submit:disabled{opacity:.6}.result{color:#236e52}@media(max-width:520px){.paper{padding:20px}.identity{grid-template-columns:1fr}}
</style>
