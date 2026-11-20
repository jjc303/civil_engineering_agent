import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  getMascotStateSpec,
  isMascotBusyState,
  resolveMascotTransition,
} from '@/mascot/stateMachine'
import { resolvePageContextPolicy } from '@/mascot/pageContextRegistry'
import { extractApiError } from '@/utils/errors'
import { mockUiConfigAdapter } from '@/api/mock/uiConfig.mock'
import { emitMockViolationEvent, mockRealtimeAdapter } from '@/api/mock/realtime.mock'

describe('Mascot FSM & Strategy Registry (OCP / Zero Hardcoding)', () => {
  it('allows higher-priority alert to preempt idle or speaking but blocks low-priority hover during alert', () => {
    const toAlert = resolveMascotTransition('idle', 'alert')
    assert.equal(toAlert.accepted, true)
    assert.equal(toAlert.nextState, 'alert')
    assert.equal(toAlert.spec.prop, 'warning_flag')
    assert.equal(toAlert.spec.beacon, 'danger')

    const hoverDuringAlert = resolveMascotTransition('alert', 'hover')
    assert.equal(hoverDuringAlert.accepted, false)
    assert.equal(hoverDuringAlert.nextState, 'alert')

    const forcedReset = resolveMascotTransition('alert', 'idle', true)
    assert.equal(forcedReset.accepted, true)
    assert.equal(forcedReset.nextState, 'idle')
  })

  it('tracks busy states and auto-revert configurations deterministically', () => {
    assert.equal(isMascotBusyState('thinking'), true)
    assert.equal(isMascotBusyState('tool_busy'), true)
    assert.equal(isMascotBusyState('confirm_pending'), true)
    assert.equal(isMascotBusyState('idle'), false)
    assert.equal(getMascotStateSpec('error').prop, 'wrench')
    assert.ok((getMascotStateSpec('success').autoRevertMs ?? 0) > 0)
  })

  it('resolves page context policies without route path hardcoding', () => {
    assert.equal(resolvePageContextPolicy('workerLearning').mode, 'hidden')
    assert.equal(resolvePageContextPolicy('copilot').mode, 'dock')
    const zonesPolicy = resolvePageContextPolicy('zones')
    assert.equal(zonesPolicy.mode, 'float')
    assert.ok(zonesPolicy.quickPromptKeys.length > 0)
    assert.equal(resolvePageContextPolicy('unknown_key').key, 'default')
  })

  it('extracts API error messages cleanly across Axios/FastAPI payloads', () => {
    assert.equal(
      extractApiError({ response: { data: { detail: 'version conflict' } } }, 'fallback'),
      'version conflict',
    )
    assert.equal(
      extractApiError({ response: { data: { detail: [{ msg: 'field A' }, { msg: 'field B' }] } } }, 'fallback'),
      'field A; field B',
    )
    assert.equal(extractApiError(new Error('network down'), 'fallback'), 'network down')
    assert.equal(extractApiError({}, 'fallback'), 'fallback')
  })

  it('provides full offline mock UI config with mascot profile and mock realtime dispatch', async () => {
    const uiConfig = await mockUiConfigAdapter.fetchAssistantUiConfig()
    assert.equal(uiConfig.mascot_profile?.enabled, true)
    assert.equal(uiConfig.mascot_profile?.persona_name, '安小盾')

    let receivedUuid = ''
    const handle = mockRealtimeAdapter.createSafetyEventStream({
      onViolationEvent(payload) {
        receivedUuid = payload.record.event_uuid
      },
    })
    emitMockViolationEvent({
      operation: 'CREATED',
      record: {
        event_uuid: 'evt-mock-1',
        camera_id: 'cam-crane-01',
        monitor_session_id: 'sess-1',
        track_id: 1,
        violation_type: 'NO_HELMET',
        severity: 'CRITICAL',
        status: 'ACTIVE',
        zone_id: null,
        zone_name: null,
        occurred_at_utc: new Date().toISOString(),
        resolved_at_utc: null,
        duration_seconds: 5,
        snapshot_uri: null,
        model_name: null,
        model_version: null,
        extra_details: {},
      },
    })
    assert.equal(receivedUuid, 'evt-mock-1')
    handle.close()
  })
})
