/**
 * Audio waveform capture and analysis utilities
 * Captures waveform data during recording for visualization
 */

export interface WaveformData {
  amplitudes: number[];  // Array of normalized amplitude values (0-1)
  sampleCount: number;   // Number of samples captured
}

export interface RecordingMetadata {
  duration: number;           // Duration in seconds
  waveformData: number[];     // Amplitude array for visualization
}

/**
 * Creates a waveform analyzer for capturing audio amplitude during recording
 */
export class WaveformAnalyzer {
  private audioContext: AudioContext;
  private analyser: AnalyserNode;
  private dataArray: Uint8Array;
  private amplitudes: number[] = [];
  private sampleInterval: number;
  private intervalId: NodeJS.Timeout | null = null;

  constructor(stream: MediaStream, sampleCount: number = 50) {
    this.audioContext = new AudioContext();
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 2048;

    const source = this.audioContext.createMediaStreamSource(stream);
    source.connect(this.analyser);

    this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);

    // Calculate sample interval to capture exactly sampleCount samples
    // Sampling every 100ms for smooth waveform
    this.sampleInterval = 100;
  }

  /**
   * Start capturing waveform data
   */
  start(): void {
    this.amplitudes = [];

    this.intervalId = setInterval(() => {
      // Get frequency data
      this.analyser.getByteFrequencyData(this.dataArray);

      // Calculate average amplitude (RMS-like)
      let sum = 0;
      for (let i = 0; i < this.dataArray.length; i++) {
        sum += this.dataArray[i];
      }
      const average = sum / this.dataArray.length;

      // Normalize to 0-1 range (0-255 -> 0-1)
      const normalized = average / 255;

      this.amplitudes.push(normalized);
    }, this.sampleInterval);
  }

  /**
   * Stop capturing and return waveform data
   */
  stop(): WaveformData {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }

    return {
      amplitudes: this.amplitudes,
      sampleCount: this.amplitudes.length
    };
  }

  /**
   * Cleanup resources
   */
  dispose(): void {
    this.stop();
    if (this.audioContext.state !== 'closed') {
      this.audioContext.close();
    }
  }
}

/**
 * Downsample waveform data to target sample count
 * Useful for reducing data size while maintaining visual fidelity
 */
export function downsampleWaveform(data: number[], targetCount: number): number[] {
  if (data.length <= targetCount) {
    return data;
  }

  const downsampled: number[] = [];
  const chunkSize = data.length / targetCount;

  for (let i = 0; i < targetCount; i++) {
    const start = Math.floor(i * chunkSize);
    const end = Math.floor((i + 1) * chunkSize);

    // Take average of chunk for smoother waveform
    let sum = 0;
    for (let j = start; j < end; j++) {
      sum += data[j];
    }
    downsampled.push(sum / (end - start));
  }

  return downsampled;
}

/**
 * Format duration in seconds to MM:SS
 */
export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
