// Unit tests for the WebUI formatting helpers.
// Run with: node --test webui/tests/
// Uses only node:test so the WebUI keeps its zero-devDependency policy.

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  cleanDisplayName,
  formatFileSize,
  extractUrl,
  isNetworkError,
  formatErrorMessage,
  shellEscape,
  needsResolutionPicker,
  isVideoExt,
  isImageExt,
  isAudioExt,
  getExtIcon
} from '../src/helpers/format.js'

test('cleanDisplayName strips real extractor id suffixes', () => {
  // Shape produced by engine/_impl.py: {title}_{media_id}
  assert.equal(
    cleanDisplayName('Rory\u2019s newest addition to her playlist_7699196133175840013.mp4'),
    'Rory\u2019s newest addition to her playlist'
  )
  assert.equal(cleanDisplayName('video_7699196133175840013.mp4'), 'video')
  assert.equal(cleanDisplayName('My Clip_a1b2c3d4.mp4'), 'My Clip')
  assert.equal(cleanDisplayName('Clip_deadbeef.mp4'), 'Clip')
})

test('cleanDisplayName strips album item index', () => {
  assert.equal(cleanDisplayName('Album_a1b2c3d4_1.jpg'), 'Album')
  assert.equal(cleanDisplayName('Album_a1b2c3d4_12.jpg'), 'Album')
})

test('cleanDisplayName preserves titles that only look like ids', () => {
  // Regression: any 8+ character run used to be treated as a media id, which
  // silently truncated real titles.
  assert.equal(cleanDisplayName('Best_Song_ABCDEFGH.mp4'), 'Best_Song_ABCDEFGH')
  assert.equal(cleanDisplayName('My Video_UPLOADED.mp4'), 'My Video_UPLOADED')
  assert.equal(cleanDisplayName('Tutorial_numbers_12345678.mp4'), 'Tutorial_numbers_12345678')
  assert.equal(cleanDisplayName('Podcast_Episode_January.mp4'), 'Podcast_Episode_January')
})

test('cleanDisplayName leaves ordinary names alone', () => {
  assert.equal(cleanDisplayName('normal.mp4'), 'normal')
  assert.equal(cleanDisplayName('a_b_123.mp4'), 'a_b_123')
  assert.equal(cleanDisplayName(''), '')
  assert.equal(cleanDisplayName(null), '')
})

test('formatFileSize handles boundaries and junk input', () => {
  assert.equal(formatFileSize(0), '')
  assert.equal(formatFileSize(-1), '')
  assert.equal(formatFileSize(null), '')
  assert.equal(formatFileSize(undefined), '')
  assert.equal(formatFileSize(1024), '1 KB')
  assert.equal(formatFileSize(1048576), '1 MB')
  assert.equal(formatFileSize(1073741824), '1.0 GB')
})

test('extractUrl strips tracking params per platform', () => {
  assert.equal(extractUrl('https://x.com/u/status/1?s=20&t=abc'), 'https://x.com/u/status/1')
  assert.equal(
    extractUrl('https://youtube.com/watch?v=abc&si=x&feature=share&pp=a'),
    'https://youtube.com/watch?v=abc&pp=a'
  )
  assert.equal(
    extractUrl('https://tiktok.com/@u/video/1?_t=a&_r=1&is_copy=1'),
    'https://tiktok.com/@u/video/1?is_copy=1'
  )
  assert.equal(extractUrl('https://instagram.com/reel/a/?igsh=x&utm_source=ig'), 'https://instagram.com/reel/a/')
  assert.equal(extractUrl('https://example.com/a?utm_source=x#frag'), 'https://example.com/a#frag')
  assert.equal(extractUrl(''), '')
})

test('extractUrl pulls the first url out of surrounding text', () => {
  assert.equal(
    extractUrl('look at https://vt.tiktok.com/abc/ ok'),
    'https://vt.tiktok.com/abc/'
  )
})

test('isNetworkError recognises transport failures only', () => {
  assert.equal(isNetworkError('urlopen error Temporary failure in name resolution'), true)
  assert.equal(isNetworkError('connection refused'), true)
  assert.equal(isNetworkError('HTTP Error 403: Forbidden'), false)
  assert.equal(isNetworkError(''), false)
  assert.equal(isNetworkError(null), false)
})

test('formatErrorMessage maps common failures', () => {
  assert.match(formatErrorMessage('urlopen error no internet'), /No internet connection/)
  assert.match(formatErrorMessage('certificate_verify_failed'), /SSL certificate/)
  assert.match(formatErrorMessage('HTTP Error 403: Forbidden'), /403/)
  assert.match(formatErrorMessage('HTTP Error 404: Not Found'), /404/)
  assert.equal(formatErrorMessage(''), 'Unknown error occurred')
})

test('shellEscape neutralises quote breakout', () => {
  assert.equal(shellEscape('plain'), "'plain'")
  assert.equal(shellEscape("it's"), "'it'\\''s'")
  const evil = "x'; touch /tmp/PWNED; echo '"
  const escaped = shellEscape(evil)
  assert.equal(escaped, "'x'\\''; touch /tmp/PWNED; echo '\\'''")
  // Inside the wrapping quotes every single quote must be part of the `'\''`
  // escape sequence, so splitting on that sequence leaves no stray quote for
  // the shell to close the string early.
  const inner = escaped.slice(1, -1)
  assert.equal(inner.split("'\\''").join('').includes("'"), false)
})

test('extension classifiers agree with getExtIcon', () => {
  assert.equal(isVideoExt('mp4'), true)
  assert.equal(isVideoExt('MP4'), true)
  assert.equal(isVideoExt('jpg'), false)
  assert.equal(isImageExt('webp'), true)
  assert.equal(isAudioExt('flac'), true)
  assert.equal(getExtIcon('mp4'), 'video')
  assert.equal(getExtIcon('mp3'), 'music')
  assert.equal(getExtIcon('jpg'), 'image')
  assert.equal(getExtIcon(''), 'image')
})

test('needsResolutionPicker only for youtube', () => {
  assert.equal(needsResolutionPicker('https://youtu.be/abc'), true)
  assert.equal(needsResolutionPicker('https://youtube.com/watch?v=a'), true)
  assert.equal(needsResolutionPicker('https://tiktok.com/x'), false)
  assert.equal(needsResolutionPicker(''), false)
})
