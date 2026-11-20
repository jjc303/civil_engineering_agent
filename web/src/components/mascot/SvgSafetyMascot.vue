<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 120 120"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    :class="['mascot-svg', `state-${state}`, { 'reduced-motion': reducedMotion, 'is-speaking': speakingActive }]"
    role="img"
    aria-hidden="true"
  >
    <defs>
      <linearGradient id="mascotHelmetGrad" x1="24" y1="16" x2="96" y2="62" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#8F7CE8" />
        <stop offset="100%" stop-color="#6559DA" />
      </linearGradient>
      <linearGradient id="mascotVestGrad" x1="34" y1="74" x2="86" y2="108" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#F59E0B" />
        <stop offset="100%" stop-color="#D97706" />
      </linearGradient>
      <linearGradient id="mascotBodyGrad" x1="34" y1="70" x2="86" y2="108" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#4B456B" />
        <stop offset="100%" stop-color="#35314F" />
      </linearGradient>
      <filter id="mascotSoftShadow" x="-15%" y="-10%" width="130%" height="135%">
        <feDropShadow dx="0" dy="4" stdDeviation="3.5" flood-color="#352F58" flood-opacity="0.22" />
      </filter>
    </defs>

    <!-- Ground shadow -->
    <ellipse class="ground-shadow" cx="60" cy="111" rx="28" ry="5" fill="#39354F" fill-opacity="0.16" />

    <!-- Alert radiating rings -->
    <g v-if="state === 'alert'" class="alert-waves">
      <circle cx="60" cy="17" r="10" stroke="#EF4444" stroke-width="2" stroke-opacity="0.65" />
      <circle cx="60" cy="17" r="16" stroke="#EF4444" stroke-width="1.5" stroke-opacity="0.35" />
    </g>

    <g class="mascot-chassis" filter="url(#mascotSoftShadow)">
      <!-- Torso / Safety Uniform -->
      <path
        d="M35 84C35 74.6 42.6 67 52 67H68C77.4 67 85 74.6 85 84V99C85 103.4 81.4 107 77 107H43C38.6 107 35 103.4 35 99V84Z"
        fill="url(#mascotBodyGrad)"
      />
      <!-- High-visibility Reflective Vest -->
      <path
        d="M41 72C41 69.2 43.2 67 46 67H53L56 79H64L67 67H74C76.8 67 79 69.2 79 72V105H41V72Z"
        fill="url(#mascotVestGrad)"
      />
      <!-- Reflective Stripes -->
      <rect x="41" y="88" width="38" height="4.5" rx="1.5" fill="#FEF3C7" fill-opacity="0.92" />
      <rect x="41" y="96.5" width="38" height="3.5" rx="1.5" fill="#FEF3C7" fill-opacity="0.82" />
      <!-- Chest Shield Badge -->
      <path d="M60 72L65 74.8V79.6C65 82.6 62.8 84.8 60 85.8C57.2 84.8 55 82.6 55 79.6V74.8L60 72Z" fill="#EDE9FE" />
      <path d="M60 74.2L63 75.9V79.1C63 81 61.7 82.4 60 83.1C58.3 82.4 57 81 57 79.1V75.9L60 74.2Z" fill="#7462D6" />

      <!-- Left Arm -->
      <g class="arm-left">
        <path
          d="M36 74C29 76 25 82 26 89C26.7 93 30.5 94.5 33.8 92.6L38 89.5"
          stroke="#433D61"
          stroke-width="8"
          stroke-linecap="round"
        />
        <circle cx="28.5" cy="90.5" r="4.5" fill="#FFE4D6" />
      </g>

      <!-- Right Arm (gestures by state) -->
      <g class="arm-right">
        <path
          d="M84 74C91 76 95 82 94 89C93.3 93 89.5 94.5 86.2 92.6L82 89.5"
          stroke="#433D61"
          stroke-width="8"
          stroke-linecap="round"
        />
        <circle cx="91.5" cy="90.5" r="4.5" fill="#FFE4D6" />
      </g>

      <!-- Neck & Head -->
      <rect x="54" y="61" width="12" height="9" rx="4" fill="#F7CDB8" />
      <rect x="36" y="34" width="48" height="34" rx="17" fill="#FFE8DC" />
      <!-- Ears / Headset pads -->
      <rect x="31.5" y="46" width="5.5" height="12" rx="2.75" fill="#6559DA" />
      <rect x="83" y="46" width="5.5" height="12" rx="2.75" fill="#6559DA" />
      <!-- Rosy cheeks -->
      <ellipse cx="43.5" cy="56.5" rx="4" ry="2.2" fill="#FDA4AF" fill-opacity="0.45" />
      <ellipse cx="76.5" cy="56.5" rx="4" ry="2.2" fill="#FDA4AF" fill-opacity="0.45" />

      <!-- Eyes & Expressions -->
      <g class="face-eyes" :transform="`translate(${gazeOffset.x}, ${gazeOffset.y})`">
        <template v-if="state === 'success'">
          <path d="M44 50.5C45.8 47.5 50.2 47.5 52 50.5" stroke="#2D2942" stroke-width="2.6" stroke-linecap="round" />
          <path d="M68 50.5C69.8 47.5 74.2 47.5 76 50.5" stroke="#2D2942" stroke-width="2.6" stroke-linecap="round" />
        </template>
        <template v-else-if="state === 'error'">
          <path d="M44 47.5L52 51.5M52 47.5L44 51.5" stroke="#2D2942" stroke-width="2.4" stroke-linecap="round" />
          <path d="M68 47.5L76 51.5M76 47.5L68 51.5" stroke="#2D2942" stroke-width="2.4" stroke-linecap="round" />
        </template>
        <template v-else>
          <g class="eye-pair">
            <ellipse cx="48" cy="49.5" rx="3.8" :ry="state === 'alert' ? 4.8 : 4.2" fill="#25213B" />
            <circle cx="49.3" cy="47.8" r="1.35" fill="#FFFFFF" />
            <ellipse cx="72" cy="49.5" rx="3.8" :ry="state === 'alert' ? 4.8 : 4.2" fill="#25213B" />
            <circle cx="73.3" cy="47.8" r="1.35" fill="#FFFFFF" />
          </g>
          <!-- Eyebrows for thinking / alert -->
          <path
            v-if="state === 'thinking' || state === 'tool_busy'"
            d="M43 43.2L52.5 44.6M67.5 44.6L77 43.2"
            stroke="#534978"
            stroke-width="2"
            stroke-linecap="round"
          />
          <path
            v-else-if="state === 'alert'"
            d="M43 44.5L52.5 42M67.5 42L77 44.5"
            stroke="#B91C1C"
            stroke-width="2.2"
            stroke-linecap="round"
          />
        </template>
      </g>

      <!-- Mouth -->
      <g class="face-mouth">
        <ellipse
          v-if="state === 'speaking' || speakingActive"
          class="mouth-speaking"
          cx="60"
          cy="59.5"
          rx="4.2"
          ry="3.1"
          fill="#9F4A54"
        />
        <circle v-else-if="state === 'alert'" cx="60" cy="59.5" r="3.4" fill="#B91C1C" />
        <circle v-else-if="state === 'listening'" cx="60" cy="59.5" r="2.3" fill="#6E5262" />
        <path
          v-else-if="state === 'error'"
          d="M54.5 60.5C56.5 58 63.5 58 65.5 60.5"
          stroke="#5A4552"
          stroke-width="2.2"
          stroke-linecap="round"
        />
        <path
          v-else-if="state === 'thinking' || state === 'tool_busy'"
          d="M56 59.5H64"
          stroke="#5A4552"
          stroke-width="2.2"
          stroke-linecap="round"
        />
        <path
          v-else
          d="M54 58.2C56.4 61.5 63.6 61.5 66 58.2"
          stroke="#5A4552"
          stroke-width="2.3"
          stroke-linecap="round"
        />
      </g>

      <!-- Safety Helmet -->
      <g class="helmet">
        <path
          d="M32 39C32 23.5 44.5 14 60 14C75.5 14 88 23.5 88 39H32Z"
          fill="url(#mascotHelmetGrad)"
        />
        <!-- Helmet Top Ridge -->
        <path d="M55 14.5C57 13.7 63 13.7 65 14.5L63.5 34H56.5L55 14.5Z" fill="#A99AEA" fill-opacity="0.85" />
        <!-- Helmet Brim -->
        <rect x="28" y="37" width="64" height="5.5" rx="2.75" fill="#5346B8" />
        <!-- Helmet Status Beacon -->
        <circle :class="['helmet-beacon', `beacon-${beacon}`]" cx="60" cy="17" r="4.5" />
        <circle cx="58.7" cy="15.8" r="1.2" fill="#FFFFFF" fill-opacity="0.8" />
      </g>

      <!-- State-driven Props -->
      <!-- 1. Safety Manual (thinking) -->
      <g v-if="prop === 'manual'" class="prop-item prop-manual">
        <rect x="76" y="75" width="22" height="17" rx="3" fill="#FFFFFF" stroke="#7462D6" stroke-width="2" />
        <line x1="87" y1="76" x2="87" y2="91" stroke="#C4B5FD" stroke-width="1.5" />
        <line x1="80" y1="81" x2="84.5" y2="81" stroke="#7462D6" stroke-width="1.6" stroke-linecap="round" />
        <line x1="89.5" y1="81" x2="94" y2="81" stroke="#7462D6" stroke-width="1.6" stroke-linecap="round" />
        <line x1="80" y1="85" x2="84.5" y2="85" stroke="#A78BFA" stroke-width="1.6" stroke-linecap="round" />
      </g>

      <!-- 2. Walkie-Talkie (tool_busy) -->
      <g v-else-if="prop === 'walkie_talkie'" class="prop-item prop-walkie">
        <rect x="87" y="72" width="12" height="20" rx="3" fill="#2D2942" stroke="#A99AEA" stroke-width="1.5" />
        <line x1="90" y1="65" x2="90" y2="72" stroke="#2D2942" stroke-width="2.2" stroke-linecap="round" />
        <rect x="89.5" y="75.5" width="7" height="5" rx="1" fill="#34D399" />
        <path d="M102 72C105 74.5 105 79.5 102 82" stroke="#8B5CF6" stroke-width="2" stroke-linecap="round" />
        <path d="M106 69.5C110 73.5 110 80.5 106 84.5" stroke="#A78BFA" stroke-width="1.8" stroke-linecap="round" />
      </g>

      <!-- 3. Pending Confirmation Clipboard (confirm_pending) -->
      <g v-else-if="prop === 'clipboard'" class="prop-item prop-clipboard">
        <rect x="78" y="68" width="22" height="26" rx="4" fill="#FFFBEB" stroke="#F59E0B" stroke-width="2" />
        <rect x="84.5" y="65" width="9" height="4.5" rx="1.5" fill="#D97706" />
        <path d="M84 79L88 83L95 75.5" stroke="#D97706" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
        <line x1="83" y1="88" x2="95" y2="88" stroke="#FCD34D" stroke-width="2" stroke-linecap="round" />
      </g>

      <!-- 4. Warning Flag (alert) -->
      <g v-else-if="prop === 'warning_flag'" class="prop-item prop-flag">
        <line x1="92" y1="58" x2="92" y2="95" stroke="#374151" stroke-width="2.6" stroke-linecap="round" />
        <path d="M92 59L111 66.5L92 74Z" fill="#EF4444" />
        <path d="M96.5 64V67.5M96.5 69.6V70.2" stroke="#FFFFFF" stroke-width="1.8" stroke-linecap="round" />
      </g>

      <!-- 5. Check / Salute Badge (success) -->
      <g v-else-if="prop === 'check_badge'" class="prop-item prop-check">
        <circle cx="93" cy="74" r="10.5" fill="#10B981" stroke="#FFFFFF" stroke-width="2" />
        <path d="M88.5 74.2L91.8 77.5L97.8 70.8" stroke="#FFFFFF" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
      </g>

      <!-- 6. Maintenance Wrench (error) -->
      <g v-else-if="prop === 'wrench'" class="prop-item prop-wrench">
        <path
          d="M89 72C92.5 70 96.5 72 97 75.5C97.4 78.2 95.8 80.5 93.4 81.2L86.5 91.5C85.8 92.6 84.3 92.8 83.2 92.1C82.1 91.4 81.9 89.9 82.6 88.8L89.5 78.5C88.3 76.4 87.9 73.8 89 72Z"
          fill="#94A3B8"
          stroke="#475569"
          stroke-width="1.4"
        />
      </g>
    </g>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getMascotStateSpec, type MascotState } from '@/mascot/stateMachine'
import type { MascotGazeOffset } from '@/mascot/renderer'

const props = withDefaults(
  defineProps<{
    state: MascotState
    gazeOffset?: MascotGazeOffset
    reducedMotion?: boolean
    hasPendingAction?: boolean
    unreadAlerts?: number
    speakingActive?: boolean
    size?: number
  }>(),
  {
    gazeOffset: () => ({ x: 0, y: 0 }),
    reducedMotion: false,
    hasPendingAction: false,
    unreadAlerts: 0,
    speakingActive: false,
    size: 86,
  },
)

const spec = computed(() => getMascotStateSpec(props.state))
const prop = computed(() => spec.value.prop)
const beacon = computed(() => spec.value.beacon)
</script>

<style scoped>
.mascot-svg {
  display: block;
  overflow: visible;
  user-select: none;
}

.mascot-chassis {
  transform-origin: 60px 95px;
  animation: mascot-float 3.4s ease-in-out infinite;
}

.ground-shadow {
  transform-origin: 60px 111px;
  animation: shadow-breathe 3.4s ease-in-out infinite;
}

.eye-pair {
  transform-origin: 60px 49.5px;
  animation: mascot-blink 4.6s ease-in-out infinite;
}

.helmet-beacon {
  transition: fill 0.25s ease;
}

.beacon-calm {
  fill: #c4b5fd;
}

.beacon-pulse {
  fill: #818cf8;
  animation: beacon-pulse 1.2s ease-in-out infinite;
}

.beacon-amber {
  fill: #fbbf24;
  animation: beacon-pulse 1s ease-in-out infinite;
}

.beacon-danger {
  fill: #ef4444;
  animation: beacon-flash 0.55s ease-in-out infinite;
}

.beacon-success {
  fill: #10b981;
}

.state-hover .mascot-chassis {
  transform: translateY(-3px);
}

.state-hover .arm-right {
  transform-origin: 84px 76px;
  animation: arm-wave 0.7s ease-in-out infinite alternate;
}

.state-thinking .mascot-chassis,
.state-tool_busy .mascot-chassis {
  animation: mascot-think 1.8s ease-in-out infinite;
}

.state-alert .mascot-chassis {
  animation: mascot-alert-bounce 0.55s ease-in-out infinite;
}

.state-alert .prop-flag {
  transform-origin: 92px 92px;
  animation: flag-wave 0.45s ease-in-out infinite alternate;
}

.state-success .mascot-chassis {
  animation: mascot-hop 0.65s ease-out 2;
}

.is-speaking .mouth-speaking,
.state-speaking .mouth-speaking {
  transform-origin: 60px 59.5px;
  animation: mouth-talk 0.28s ease-in-out infinite alternate;
}

.alert-waves circle {
  transform-origin: 60px 17px;
  animation: wave-ring 1.1s ease-out infinite;
}

.reduced-motion .mascot-chassis,
.reduced-motion .ground-shadow,
.reduced-motion .eye-pair,
.reduced-motion .helmet-beacon,
.reduced-motion .arm-right,
.reduced-motion .prop-flag,
.reduced-motion .mouth-speaking,
.reduced-motion .alert-waves circle {
  animation: none !important;
}

@keyframes mascot-float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-3px); }
}

@keyframes shadow-breathe {
  0%, 100% { transform: scaleX(1); opacity: 0.16; }
  50% { transform: scaleX(0.92); opacity: 0.11; }
}

@keyframes mascot-blink {
  0%, 92%, 100% { transform: scaleY(1); }
  96% { transform: scaleY(0.12); }
}

@keyframes mascot-think {
  0%, 100% { transform: rotate(-1.5deg) translateY(0); }
  50% { transform: rotate(1.5deg) translateY(-2px); }
}

@keyframes mascot-alert-bounce {
  0%, 100% { transform: translateY(0) scale(1); }
  50% { transform: translateY(-4.5px) scale(1.02); }
}

@keyframes mascot-hop {
  0%, 100% { transform: translateY(0); }
  45% { transform: translateY(-6px); }
}

@keyframes arm-wave {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(-16deg); }
}

@keyframes flag-wave {
  0% { transform: rotate(-8deg); }
  100% { transform: rotate(10deg); }
}

@keyframes mouth-talk {
  0% { transform: scaleY(0.55); }
  100% { transform: scaleY(1.15); }
}

@keyframes beacon-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}

@keyframes beacon-flash {
  0%, 100% { opacity: 1; transform: scale(1.12); }
  50% { opacity: 0.35; transform: scale(0.92); }
}

@keyframes wave-ring {
  0% { transform: scale(0.7); opacity: 0.75; }
  100% { transform: scale(1.65); opacity: 0; }
}
</style>
