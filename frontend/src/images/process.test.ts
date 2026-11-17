import { describe, expect, it } from 'vitest'
import { hashBlob, planImage } from './process'

describe('image processing decisions', () => {
  it('keeps a small image as it is', () => {
    expect(planImage('image/png', 200_000, 800, 600)).toEqual({
      width: 800,
      height: 600,
      reencode: false,
    })
  })

  it('re-encodes an image over 1 MB without resizing it', () => {
    expect(planImage('image/jpeg', 3_000_000, 2000, 1500)).toEqual({
      width: 2000,
      height: 1500,
      reencode: true,
    })
  })

  it('scales the longer edge down to 2560 px', () => {
    expect(planImage('image/jpeg', 500_000, 4032, 3024)).toEqual({
      width: 2560,
      height: 1920,
      reencode: true,
    })
    expect(planImage('image/webp', 500_000, 1000, 5120)).toEqual({
      width: 500,
      height: 2560,
      reencode: true,
    })
  })

  it('never re-encodes a GIF', () => {
    expect(planImage('image/gif', 5_000_000, 4000, 4000)).toEqual({
      width: 4000,
      height: 4000,
      reencode: false,
    })
  })

  it('hashes bytes with SHA-256 in hex', async () => {
    expect(await hashBlob(new Blob(['abc']))).toBe(
      'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    )
  })
})
