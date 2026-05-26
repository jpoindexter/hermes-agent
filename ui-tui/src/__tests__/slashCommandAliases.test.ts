import { describe, expect, it } from 'vitest'

import { findSlashCommand } from '../app/slash/registry.js'

describe('slash command alias resolution', () => {
  it('/q resolves to queue, not quit', () => {
    const cmd = findSlashCommand('q')
    expect(cmd).toBeDefined()
    expect(cmd?.name).toBe('queue')
  })

  it('/exit still resolves to quit', () => {
    const cmd = findSlashCommand('exit')
    expect(cmd).toBeDefined()
    expect(cmd?.name).toBe('quit')
  })

  it('/quit resolves to quit', () => {
    const cmd = findSlashCommand('quit')
    expect(cmd).toBeDefined()
    expect(cmd?.name).toBe('quit')
  })

  it('/queue resolves to queue', () => {
    const cmd = findSlashCommand('queue')
    expect(cmd).toBeDefined()
    expect(cmd?.name).toBe('queue')
  })
})
