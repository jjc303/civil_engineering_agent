import assert from 'node:assert/strict'
import { afterEach, describe, it } from 'node:test'
import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios'
import { CHAT_ENDPOINT, createApiClient, notifyHttpError, resolveMediaUrl } from '@/api/client'
import {
  registerApiNotifier,
  registerApiTranslator,
  resetApiNotifier,
  resetApiTranslator,
  type ApiNotifier,
} from '@/api/ports'

function buildAxiosError(status?: number, url = '/api/v1/zones', data?: unknown): AxiosError {
  const config: InternalAxiosRequestConfig = {
    url,
    headers: new AxiosHeaders(),
  }
  const response = status
    ? {
        status,
        statusText: String(status),
        headers: {},
        config,
        data,
      }
    : undefined
  return new AxiosError('Request failed', 'ERR_BAD_RESPONSE', config, undefined, response as never)
}

describe('API infrastructure DIP (no Element Plus dependency)', () => {
  afterEach(() => {
    resetApiNotifier()
    resetApiTranslator()
  })

  it('does not throw when default noop notifier is active', () => {
    assert.doesNotThrow(() => {
      notifyHttpError(buildAxiosError(500, '/api/v1/cameras', { detail: 'Internal error' }))
    })
  })

  it('dispatches localized notifications through injected ApiNotifier and ApiTranslator', () => {
    const errors: string[] = []
    const warnings: string[] = []
    const notifier: ApiNotifier = {
      error: (msg) => errors.push(msg),
      warning: (msg) => warnings.push(msg),
    }

    registerApiNotifier(notifier)
    registerApiTranslator((key, params) => `${key}:${JSON.stringify(params ?? {})}`)

    notifyHttpError(buildAxiosError(409, '/api/v1/cameras/cam-1/zones', { detail: 'version conflict' }))
    notifyHttpError(buildAxiosError(422, '/api/v1/violations', { detail: [{ msg: 'bad field' }] }))
    notifyHttpError(buildAxiosError(502, '/api/v1/cameras', { detail: 'upstream down' }))
    notifyHttpError(buildAxiosError(undefined, '/api/v1/cameras'))
    notifyHttpError(buildAxiosError(404, '/api/v1/cameras/missing'))
    notifyHttpError(buildAxiosError(500, CHAT_ENDPOINT, { detail: 'handled by chat UI' }))

    assert.equal(errors.length, 3)
    assert.equal(warnings.length, 1)
    assert.match(errors[0]!, /^errors\.versionConflict:.*version conflict/)
    assert.match(warnings[0]!, /^errors\.validationError:.*bad field/)
    assert.match(errors[1]!, /^errors\.serverError:.*502/)
    assert.match(errors[2]!, /^errors\.networkError:/)
  })

  it('injects Accept-Language header on outgoing client requests in pure Node', async () => {
    const client = createApiClient()
    let seenHeader: unknown
    client.defaults.adapter = async (config) => {
      seenHeader = config.headers?.get?.('Accept-Language') ?? config.headers?.['Accept-Language']
      return {
        data: { ok: true },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }

    await client.get('/api/v1/cameras')
    assert.ok(seenHeader === 'zh-CN' || seenHeader === 'zh-HK')
  })

  it('resolves media snapshot URIs safely', () => {
    assert.equal(resolveMediaUrl(null), '')
    assert.equal(resolveMediaUrl('/snapshots/a.jpg'), '/media/snapshots/a.jpg')
    assert.equal(resolveMediaUrl('snapshots/a.jpg'), '/media/snapshots/a.jpg')
  })
})
