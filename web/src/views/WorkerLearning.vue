<template>
  <main class="worker-page">
    <article class="paper" v-if="task">
      <div class="paper-top">
        <div class="brand">{{ t('workerLearn.brand') }}</div>
        <LocaleToggle
          compact
          :model-value="locale"
          :options="localeOptions"
          :label="t('app.localeSwitchLabel')"
          @select="setLocale"
        />
      </div>
      <h1>{{ task.title }}</h1>
      <section><h2>{{ t('workerLearn.studyMaterial') }}</h2><p class="material">{{ task.material }}</p></section>
      <section v-if="!result">
        <h2>{{ t('workerLearn.quizHeading') }}</h2>
        <div v-for="(question, index) in task.questions" :key="index" class="question">
          <strong>{{ index + 1 }}. {{ question.stem }}</strong>
          <label v-for="(option, optionIndex) in question.options" :key="optionIndex">
            <input v-model="answers[index]" type="radio" :name="`q${index}`" :value="optionIndex" />{{ String.fromCharCode(65 + optionIndex) }}. {{ option }}
          </label>
        </div>
        <h2>{{ t('workerLearn.identityHeading') }}</h2>
        <div class="identity">
          <label>{{ t('workerLearn.workerIdLabel') }}<input v-model.trim="workerId" autocomplete="off" :placeholder="t('workerLearn.workerIdPlaceholder')" /></label>
          <label>{{ t('workerLearn.workerNameLabel') }}<input v-model.trim="workerName" autocomplete="name" :placeholder="t('workerLearn.workerNamePlaceholder')" /></label>
        </div>
        <p class="hint">{{ t('workerLearn.submitOnceHint') }}</p>
        <button class="submit" :disabled="busy" @click="submit">{{ busy ? t('workerLearn.submitting') : t('workerLearn.submitAnswers') }}</button>
      </section>
      <section v-else class="result">
        <h2>{{ t('workerLearn.submitSuccess') }}</h2>
        <p>{{ t('workerLearn.scoreLabel') }}<strong>{{ t('workerLearn.scoreValue', { score: result.score }) }}</strong></p>
        <p>{{ result.passed ? t('workerLearn.passedText') : t('workerLearn.failedText') }}</p>
      </section>
    </article>
    <article v-else class="paper">
      <div class="paper-top">
        <div class="brand">{{ t('workerLearn.brand') }}</div>
        <LocaleToggle
          compact
          :model-value="locale"
          :options="localeOptions"
          :label="t('app.localeSwitchLabel')"
          @select="setLocale"
        />
      </div>
      <h1>{{ loadFailed ? t('workerLearn.taskNotFound') : t('workerLearn.loadingTask') }}</h1>
    </article>
  </main>
</template>
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getPublicTraining, submitTraining } from '@/api/learning'
import LocaleToggle from '@/components/LocaleToggle.vue'
import { useAppI18n, useLocaleRefresh } from '@/i18n/useAppI18n'
import { syncDocumentTitle } from '@/router'

const route = useRoute()
const token = String(route.params.token || '')
const { t, locale, localeOptions, setLocale } = useAppI18n()
const task = ref<Awaited<ReturnType<typeof getPublicTraining>> | null>(null)
const answers = ref<number[]>([])
const workerId = ref(''), workerName = ref(''), busy = ref(false), loadFailed = ref(false)
const result = ref<{ score: number; passed: boolean } | null>(null)

async function loadTask() {
  try {
    const fetched = await getPublicTraining(token)
    task.value = fetched
    loadFailed.value = false
    if (answers.value.length !== fetched.questions.length) {
      answers.value = fetched.questions.map(() => -1)
    }
  } catch {
    loadFailed.value = true
  }
}

onMounted(() => { void loadTask() })
useLocaleRefresh(loadTask)
watch(locale, () => { syncDocumentTitle(route) })

async function submit() {
  if (!workerId.value || !workerName.value) return ElMessage.warning(t('workerLearn.fillIdentityWarning'))
  if (answers.value.some(x => x < 0)) return ElMessage.warning(t('workerLearn.completeAllWarning'))
  busy.value = true
  try {
    result.value = await submitTraining(token, { worker_id: workerId.value, worker_name: workerName.value, answers: answers.value })
  } catch {
    ElMessage.error(t('workerLearn.submitFailed'))
  } finally {
    busy.value = false
  }
}
</script>
<style scoped>
.worker-page{min-height:100dvh;background:#eef2f7;padding:24px 12px;color:#263244}.paper{max-width:680px;margin:auto;background:white;border-radius:20px;padding:30px;box-shadow:0 8px 35px #253b5314}.paper-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px}.brand{color:#5876b1;font-weight:700;letter-spacing:.08em}.paper h1{font-size:26px}.paper h2{font-size:19px;margin-top:30px}.material{white-space:pre-wrap;line-height:1.85}.question{padding:16px 0;border-bottom:1px solid #e5eaf0}.question label{display:block;padding:11px 7px;line-height:1.5}.question input{margin-right:10px;accent-color:#3869d4}.identity{display:grid;grid-template-columns:1fr 1fr;gap:12px}.identity label{display:grid;gap:7px}.identity input{font:inherit;padding:11px;border:1px solid #c9d3e2;border-radius:9px;min-width:0}.hint{color:#7e8a9b;font-size:13px}.submit{width:100%;border:0;background:#3869d4;color:white;padding:14px;border-radius:10px;font:inherit;font-weight:700}.submit:disabled{opacity:.6}.result{color:#236e52}@media(max-width:520px){.paper{padding:20px}.identity{grid-template-columns:1fr}}
</style>
