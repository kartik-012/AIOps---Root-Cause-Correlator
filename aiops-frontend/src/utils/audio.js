/**
 * Apple-grade procedural Web Audio API sound synthesizer.
 * Generates futuristic, high-fidelity UI audio feedback without any external audio files.
 */

let audioCtx = null

function getAudioContext() {
  if (!audioCtx) {
    const AudioContext = window.AudioContext || window.webkitAudioContext
    if (AudioContext) {
      audioCtx = new AudioContext()
    }
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume()
  }
  return audioCtx
}

export const sound = {
  muted: false,

  toggleMute() {
    this.muted = !this.muted
    return this.muted
  },

  // Subtle glass UI click
  click() {
    if (this.muted) return
    const ctx = getAudioContext()
    if (!ctx) return
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(800, ctx.currentTime)
    osc.frequency.exponentialRampToValueAtTime(400, ctx.currentTime + 0.04)
    gain.gain.setValueAtTime(0.08, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.04)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.04)
  },

  // Anomaly alert chord
  alert() {
    if (this.muted) return
    const ctx = getAudioContext()
    if (!ctx) return
    const freqs = [380, 570, 760]
    freqs.forEach((f, i) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'triangle'
      osc.frequency.setValueAtTime(f, ctx.currentTime + i * 0.05)
      gain.gain.setValueAtTime(0.12, ctx.currentTime + i * 0.05)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35)
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start(ctx.currentTime + i * 0.05)
      osc.stop(ctx.currentTime + 0.35)
    })
  },

  // Warm resolution / approval chord
  success() {
    if (this.muted) return
    const ctx = getAudioContext()
    if (!ctx) return
    const freqs = [523.25, 659.25, 783.99, 1046.5] // C Major chord
    freqs.forEach((f, i) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.setValueAtTime(f, ctx.currentTime + i * 0.06)
      gain.gain.setValueAtTime(0.1, ctx.currentTime + i * 0.06)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5)
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start(ctx.currentTime + i * 0.06)
      osc.stop(ctx.currentTime + 0.5)
    })
  },

  // Futuristic sweep on simulation or tab switch
  whoosh() {
    if (this.muted) return
    const ctx = getAudioContext()
    if (!ctx) return
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(300, ctx.currentTime)
    osc.frequency.exponentialRampToValueAtTime(1200, ctx.currentTime + 0.15)
    gain.gain.setValueAtTime(0.06, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.15)
  },
}
