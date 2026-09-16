// Captures the microphone in fixed chunks and hands them to the page.
//
// Both AssemblyAI connections are fed from here, from the same samples, so the
// conversation the agent hears and the word timings the verdict rests on can
// never drift apart. 1200 samples at 24 kHz is 50 ms, the chunk size both APIs
// expect.
class PcmChunker extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(1200);
    this.filled = 0;
  }

  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;
    for (let i = 0; i < input.length; i++) {
      this.buffer[this.filled++] = input[i];
      if (this.filled === this.buffer.length) {
        this.port.postMessage(this.buffer.slice());
        this.filled = 0;
      }
    }
    return true;
  }
}

registerProcessor("pcm-chunker", PcmChunker);
