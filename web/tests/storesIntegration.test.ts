import assert from 'node:assert/strict'
import { afterEach, beforeEach, describe, it } from 'node:test'
import { createPinia, setActivePinia } from 'pinia'
import { registerRealtimePort, resetRealtimePort } from '@/api/index'
import { emitMockViolationEvent, mockRealtimeAdapter } from '@/api/mock/realtime.mock'
import { registerSpeechPort, resetSpeechPort, type SpeechPort } from '@/mascot/speech'
import { useCopilotStore } from '@/stores/copilot'
import { useMascotStore } from '@/stores/mascot'
import { useRealtimeStore } from '@/stores/realtime'

describe('Pinia Stores Integration (Observer / Facade / DIP)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    registerRealtimePort(mockRealtimeAdapter)
  })

  afterEach(() => {
    resetSpeechPort()
    resetRealtimePort()
  })

  it('fans out realtime violation events to multiple subscribers over one subscription lifecycle', () => {
    const realtime = useRealtimeStore()
    const seenA: string[] = []
    const seenB: string[] = []

    const unsubA = realtime.subscribe({
      onViolationEvent(payload) {
        seenA.push(payload.record.event_uuid)
      },
    })
    const unsubB = realtime.subscribe({
      onViolationEvent(payload) {
        seenB.push(payload.record.event_uuid)
      },
    })

    emitMockViolationEvent({
      operation: 'CREATED',
      record: {
        event_uuid: 'evt-fanout-1',
        camera_id: 'cam-01',
        monitor_session_id: 'sess-1',
        track_id: 2,
        violation_type: 'DANGER_ZONE_INTRUSION',
        severity: 'CRITICAL',
        status: 'ACTIVE',
        zone_id: 'zone-1',
        zone_name: '塔吊区',
        occurred_at_utc: new Date().toISOString(),
        resolved_at_utc: null,
        duration_seconds: 12,
        snapshot_uri: null,
        model_name: null,
        model_version: null,
        extra_details: {},
      },
    })

    assert.deepEqual(seenA, ['evt-fanout-1'])
    assert.deepEqual(seenB, ['evt-fanout-1'])

    unsubA()
    emitMockViolationEvent({
      operation: 'CREATED',
      record: {
        event_uuid: 'evt-fanout-2',
        camera_id: 'cam-01',
        monitor_session_id: 'sess-1',
        track_id: 3,
        violation_type: 'NO_HELMET',
        severity: 'WARNING',
        status: 'ACTIVE',
        zone_id: null,
        zone_name: null,
        occurred_at_utc: new Date().toISOString(),
        resolved_at_utc: null,
        duration_seconds: 3,
        snapshot_uri: null,
        model_name: null,
        model_version: null,
        extra_details: {},
      },
    })

    assert.deepEqual(seenA, ['evt-fanout-1'])
    assert.deepEqual(seenB, ['evt-fanout-1', 'evt-fanout-2'])
    unsubB()
  })

  it('transitions mascot to alert, increments unread count, and speaks via injected SpeechPort', () => {
    const spoken: Array<{ text: string; locale: string }> = []
    const fakeSpeech: SpeechPort = {
      isSupported: () => true,
      speak(text, locale, onEnd) {
        spoken.push({ text, locale })
        onEnd?.()
        return true
      },
      stop() {},
    }
    registerSpeechPort(fakeSpeech)

    const mascot = useMascotStore()
    mascot.init()
    mascot.toggleVoice()
    assert.equal(mascot.voiceEnabled, true)

    emitMockViolationEvent({
      operation: 'CREATED',
      record: {
        event_uuid: 'evt-mascot-1',
        camera_id: 'cam-gate-02',
        monitor_session_id: 'sess-2',
        track_id: 7,
        violation_type: 'NO_HELMET',
        severity: 'CRITICAL',
        status: 'ACTIVE',
        zone_id: null,
        zone_name: null,
        occurred_at_utc: new Date().toISOString(),
        resolved_at_utc: null,
        duration_seconds: 4,
        snapshot_uri: null,
        model_name: null,
        model_version: null,
        extra_details: {},
      },
    })

    assert.equal(mascot.state, 'alert')
    assert.equal(mascot.unreadAlerts, 1)
    assert.ok(mascot.bubble !== null)
    assert.equal(spoken.length, 1)

    mascot.openDrawer()
    assert.equal(mascot.unreadAlerts, 0)
    assert.equal(mascot.bubble, null)
    mascot.dispose()
  })

  it('guards useCopilotStore.handleSend against DOM event arguments and preserves pageContext', async () => {
    const copilot = useCopilotStore()
    copilot.setPageContext({ route_key: 'zones', route_title: '危险区域标定', camera_id: 'cam-01' })
    copilot.inputQuestion = ''

    // Passing a non-string (e.g., DOM PointerEvent from @click="handleSend") must not throw
    await copilot.handleSend({ type: 'click' } as unknown as string)
    assert.equal(copilot.messages.length, 0)
    assert.equal(copilot.pageContext?.route_key, 'zones')
  })
})
