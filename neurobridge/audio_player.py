"""Windows audio worker: bundled decoder and native WAV output, no media app."""
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path
from platform_support import worker_options


def main():
    import imageio_ffmpeg
    import winsound
    decode_only='--decode-only' in sys.argv
    decoder = None
    with tempfile.TemporaryDirectory(prefix='neurobridge-audio-') as tmp:
        wav = Path(tmp)/'playback.wav'
        try:
            decoder = subprocess.Popen([imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-v', 'error', '-y', '-i', sys.argv[1], '-vn', '-acodec', 'pcm_s16le', '-ac', '2', '-ar', '44100', str(wav)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **worker_options())
            # communicate drains stderr, avoiding a full-pipe deadlock on invalid media.
            while True:
                try:
                    _, error = decoder.communicate(timeout=.1); break
                except subprocess.TimeoutExpired: pass
            if decoder.returncode: raise RuntimeError(error.decode('utf-8', 'replace')[:500])
            with wave.open(str(wav)) as audio: duration = audio.getnframes()/audio.getframerate()
            if decode_only:
                print('Decoded audio OK; duration %.6f seconds' % duration,flush=True)
                return
            winsound.PlaySound(str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            deadline = time.monotonic()+duration
            while time.monotonic() < deadline: time.sleep(.05)
        finally:
            winsound.PlaySound(None, 0)
            if decoder and decoder.poll() is None:
                decoder.terminate(); decoder.wait(timeout=5)


if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt: pass
