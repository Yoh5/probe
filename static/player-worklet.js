// Plays the agent's voice as it arrives.
//
// The agent sends 24 kHz PCM in small pieces, faster than real time. Scheduling
// each piece as its own buffer leaves audible seams, so they are written into
// one ring buffer and read at the output rate. `flush` empties it instantly,
// which is what barge-in needs: when the candidate interrupts, the half-spoken
// sentence must stop, not drain.
const CAPACITY = 24000 * 30; // thirty seconds is far more than the agent ever queues

class Player extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ring = new Float32Array(CAPACITY);
    this.read = 0;
    this.write = 0;
    this.port.onmessage = ({ data }) => {
      if (data === "flush") {
        this.read = this.write = 0;
        return;
      }
      for (let i = 0; i < data.length; i++) {
        this.ring[this.write % CAPACITY] = data[i];
        this.write++;
      }
    };
  }

  process(_inputs, outputs) {
    const out = outputs[0][0];
    for (let i = 0; i < out.length; i++) {
      out[i] = this.read < this.write ? this.ring[this.read++ % CAPACITY] : 0;
    }
    // Tell the page whether anything is still playing, so it can show "speaking".
    this.port.postMessage(this.read < this.write);
    return true;
  }
}

registerProcessor("agent-player", Player);
