<template>
  <EvidenceModal v-model="modalState.evidenceVisible" :record="modalState.selectedViolation" />
  <CopilotReportDetailDialog
    v-model="modalState.reportDetailOpen"
    :report-id="modalState.selectedReportId"
    @preview-pdf="previewReportPdf"
  />
  <CopilotTrainingDetailDialog
    v-model="modalState.trainingDetailOpen"
    :training-id="modalState.selectedTrainingId"
  />
  <RectificationCreateDialog
    v-model="modalState.rectificationDialogVisible"
    :target="modalState.selectedRectificationTarget"
    @proposed="onRectificationProposed"
  />
  <TrainingSetupDialog
    v-model="modalState.trainingSetupDialogVisible"
    :target="modalState.selectedTrainingReport"
    @proposed="onTrainingProposed"
  />
</template>

<script setup lang="ts">
import EvidenceModal from '@/components/EvidenceModal.vue'
import CopilotReportDetailDialog from '@/components/copilot/CopilotReportDetailDialog.vue'
import CopilotTrainingDetailDialog from '@/components/copilot/CopilotTrainingDetailDialog.vue'
import RectificationCreateDialog from '@/components/copilot/RectificationCreateDialog.vue'
import TrainingSetupDialog from '@/components/copilot/TrainingSetupDialog.vue'
import { useCopilotModals } from '@/composables/useCopilotModals'

const { modalState, previewReportPdf, onRectificationProposed, onTrainingProposed } = useCopilotModals()
</script>
