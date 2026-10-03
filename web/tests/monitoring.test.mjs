import test from 'node:test'
import assert from 'node:assert/strict'
import { cameraPage, cameraSelection, todayWindow, utcDate, filterCameras } from '../src/utils/monitoring.ts'
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
