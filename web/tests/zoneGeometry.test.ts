import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  ZONE_GEOMETRY_CONSTANTS,
  canvasPointToSource,
  computeCanvasDimensions,
  computeNextPolygonPoint,
  createDefaultZone,
  hitTestPolygonVertex,
  scalePolygonToResolution,
} from '@/utils/zoneGeometry'

describe('zoneGeometry pure utilities', () => {
  it('creates proportional default zones adapted to target resolution', () => {
    const zone = createDefaultZone(2, 'Zone 2', { width: 1280, height: 720 })
    assert.equal(zone.zone_id, 'zone-2')
    assert.equal(zone.zone_name, 'Zone 2')
    assert.equal(zone.polygon.length, 4)
    assert.ok(zone.polygon.every(([x, y]) => x >= 0 && x <= 1280 && y >= 0 && y <= 720))
  })

  it('computes responsive canvas height preserving aspect ratio', () => {
    const dims = computeCanvasDimensions(960, { width: 1920, height: 1080 })
    assert.deepEqual(dims, { width: 960, height: 540 })

    const fallback = computeCanvasDimensions(0, { width: 1920, height: 1080 })
    assert.equal(fallback.width, ZONE_GEOMETRY_CONSTANTS.fallbackCanvasWidth)
  })

  it('scales polygon coordinates across source resolution changes', () => {
    const scaled = scalePolygonToResolution(
      [
        [960, 540],
        [1920, 1080],
      ],
      { width: 1920, height: 1080 },
      { width: 1280, height: 720 },
    )
    assert.deepEqual(scaled, [
      [640, 360],
      [1280, 720],
    ])
  })

  it('clamps new polygon points to dynamic source resolution bounds', () => {
    const next = computeNextPolygonPoint([[1250, 700]], { width: 1280, height: 720 })
    assert.ok(next[0] <= 1240)
    assert.ok(next[1] <= 680)
  })

  it('performs accurate vertex hit-testing and clamped canvas-to-source conversion', () => {
    const polygon: [number, number][] = [
      [200, 100],
      [800, 400],
    ]
    assert.equal(hitTestPolygonVertex(polygon, 105, 52, 0.5, 0.5, 12), 0)
    assert.equal(hitTestPolygonVertex(polygon, 50, 50, 0.5, 0.5, 12), -1)

    const point = canvasPointToSource(1200, -10, 0.5, 0.5, { width: 1920, height: 1080 })
    assert.deepEqual(point, [1920, 0])
  })
})
