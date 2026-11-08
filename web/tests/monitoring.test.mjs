import test from 'node:test'
import assert from 'node:assert/strict'
import {
  cameraPage,
  cameraSelection,
  todayWindow,
  utcDate,
  filterCameras,
  applyRealtimeCameraStatus,
  applyRealtimeViolationEvent,
} from '../src/utils/monitoring.ts'
const cameras = Array.from({ length: 9 }, (_, i) => ({ camera_id: `camera-${i + 1}` }))
test('enlarging a later camera retains that camera, never silently shows first', () => {
  assert.deepEqual(cameraPage(cameras, 1, 1, 'camera-7'), [cameras[6]])
  assert.deepEqual(cameraPage(cameras, 1, 1, 'missing'), [])
})
test('paging does not lose cameras after first four or six', () => {
  assert.deepEqual(cameraPage(cameras, 4, 3, ''), [cameras[8]])
  assert.deepEqual(cameraPage(cameras, 6, 2, ''), cameras.slice(6))
})
test('selection survives refresh and falls back only when the selected camera disappears', () => {
  assert.equal(cameraSelection(cameras, 'camera-7'), 'camera-7')
  assert.equal(cameraSelection(cameras, 'deleted'), 'camera-1')
  assert.equal(cameraSelection([], 'deleted'), '')
})
test('daily statistics use local midnight, not a rolling 24 hour window', () => {
  const now = new Date(2026, 9, 3, 15, 12, 0)
  const value = todayWindow(now)
  assert.equal(value.start_time_utc, new Date(2026, 9, 3, 0, 0, 0).toISOString())
  assert.equal(value.end_time_utc, now.toISOString())
  assert.equal(now.getHours(), 15)
})

test('UTC API timestamps without an offset retain UTC meaning', () => {
  assert.equal(utcDate('2026-10-03T07:50:01').toISOString(), '2026-10-03T07:50:01.000Z')
  assert.equal(utcDate('2026-10-03T15:50:01+08:00').toISOString(), '2026-10-03T07:50:01.000Z')
})

test('camera search combines status and names without changing the original list', () => {
  const list = [
    {camera_id: 'CAM-01', is_online: true, extra_details: {location: '南门'}},
    {camera_id: 'CAM-02', is_online: false, extra_details: {}},
    {camera_id: 'CAM-03', is_online: true, extra_details: {}},
  ]
  assert.deepEqual(filterCameras(list, '  cam  ', 'offline'), [list[1]])
  assert.deepEqual(filterCameras(list, '南门', 'online'), [list[0]])
  assert.deepEqual(filterCameras(list, '南门', 'offline'), [])
  assert.equal(list.length, 3)
})
test('filtered single-camera selection never displays a hidden camera', () => {
  const list = [{camera_id:'one',is_online:true},{camera_id:'two',is_online:false}]
  const visible = filterCameras(list, '', 'online')
  const selected = cameraSelection(visible, 'two')
  assert.equal(selected, 'one')
  assert.deepEqual(cameraPage(visible, 1, 1, selected), [list[0]])
})

test('applyRealtimeCameraStatus updates existing camera in place or appends new camera', () => {
  const initial = [
    { camera_id: 'CAM-01', is_online: true, fps: 15 },
    { camera_id: 'CAM-02', is_online: false, fps: 0 },
  ]
  const updated = applyRealtimeCameraStatus(initial, { camera_id: 'CAM-02', is_online: true, fps: 24 })
  assert.equal(updated.length, 2)
  assert.equal(updated[1].is_online, true)
  assert.equal(updated[1].fps, 24)

  const appended = applyRealtimeCameraStatus(updated, { camera_id: 'CAM-03', is_online: true, fps: 20 })
  assert.equal(appended.length, 3)
  assert.equal(appended[2].camera_id, 'CAM-03')
})

test('applyRealtimeViolationEvent prepends new active event, updates existing, and removes resolved', () => {
  const ev1 = { event_uuid: 'u-1', status: 'ACTIVE', duration_seconds: 1.0 }
  const ev2 = { event_uuid: 'u-2', status: 'ACTIVE', duration_seconds: 2.0 }

  // 1. Prepend new ACTIVE event
  const step1 = applyRealtimeViolationEvent([ev1], 1, ev2, 6)
  assert.equal(step1.eventTotal, 2)
  assert.deepEqual(step1.events.map(e => e.event_uuid), ['u-2', 'u-1'])

  // 2. Idempotent update of existing ACTIVE event
  const ev2Updated = { event_uuid: 'u-2', status: 'ACTIVE', duration_seconds: 5.5 }
  const step2 = applyRealtimeViolationEvent(step1.events, step1.eventTotal, ev2Updated, 6)
  assert.equal(step2.eventTotal, 2)
  assert.equal(step2.events[0].duration_seconds, 5.5)

  // 3. Remove event when status transitions to RESOLVED
  const ev2Resolved = { event_uuid: 'u-2', status: 'RESOLVED', duration_seconds: 6.0 }
  const step3 = applyRealtimeViolationEvent(step2.events, step2.eventTotal, ev2Resolved, 6)
  assert.equal(step3.eventTotal, 1)
  assert.deepEqual(step3.events.map(e => e.event_uuid), ['u-1'])
})
