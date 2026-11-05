"""ACX technical profile tests use synthetic audio only."""
import math
import shutil
import struct
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

from app.audio_retailer import _constant_bitrate, check_track, ACX_PROFILE


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg required")
class RetailerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.wav = Path(self.temp.name) / "synthetic.wav"
        self.mp3 = Path(self.temp.name) / "synthetic.mp3"
        with wave.open(str(self.wav), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16000)
            out.writeframes(b"".join(
                struct.pack("<h", int(4200 * math.sin(2*math.pi*330*n/16000)))
                for n in range(16000*3)))
        subprocess.run(
            [shutil.which("ffmpeg"), "-v", "error", "-nostdin", "-y",
             "-i", str(self.wav), "-ar", "44100", "-ac", "1",
             "-codec:a", "libmp3lame", "-b:a", "192k", str(self.mp3)],
            check=True, timeout=40,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_acx_profile_matches_official_rms_peak_and_encoding_limits(self):
        self.assertEqual(ACX_PROFILE["rms_min_dbfs"], -23)
        self.assertEqual(ACX_PROFILE["sample_peak_max_dbfs"], -3)
        self.assertTrue(_constant_bitrate(self.mp3))
        result = check_track(self.mp3)
        self.assertTrue(result["checks"]["encoding"]["passed"])
        self.assertTrue(result["checks"]["sample_rate"]["passed"])
        self.assertTrue(result["checks"]["constant_bitrate"]["passed"])
        self.assertIsNotNone(result["checks"]["sample_peak"]["observed"])
        self.assertFalse(result["technical_preflight_passed"])
        self.assertIsNone(result["checks"]["noise_residual"]["passed"])

    def test_wav_not_falsely_approved_as_acx_upload(self):
        result = check_track(self.wav)
        self.assertFalse(result["checks"]["encoding"]["passed"])
        self.assertFalse(result["technical_preflight_passed"])


if __name__ == "__main__":
    unittest.main()
