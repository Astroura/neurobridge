# NeuroBridge for Mac

Local Muse 2 EEG recording and passage-comprehension experiments.

## For participants and project partners

1. Download the ZIP for your Mac from [Releases](https://github.com/Astroura/neurobridge/releases): **arm64** for Apple Silicon; **x86_64** for Intel. Extract it and move **NeuroBridge.app** to Applications.
2. Open the app. Select **Choose recording folder…** to choose where recordings will be saved. The default is `~/Documents/NeuroBridge Data`. Switching folders does not move existing recordings.
3. Turn on the Muse, close other apps connected to it, and press **Connect Muse**. Allow Bluetooth access when macOS asks. If it was denied, enable NeuroBridge in System Settings → Privacy & Security → Bluetooth and reopen the app.
4. Add reviewed audio, two questions per clip, correct answer keys, and a coded participant ID. Mark the practice passage. **Save setup on this Mac** stores this configuration in the recording folder; Restore recovers it after relaunch.
5. Press **Start session**. EEG must arrive before the baseline begins. Practice runs first, followed by randomized experimental clips. Remain silent during listening. The app plays audio through the Mac's selected audio output.
6. After the session, inspect **Recording studio** graphs or choose **Matplotlib report**. **Export all data & scientific plots…** opens a native folder picker and writes one uniquely named ZIP containing all data from the currently selected recording folder.

The native window runs a server on a random loopback port. Do not share that address; other Macs run their own app. No data are uploaded. Export only the participants you intend to share by keeping studies in separate folders.

## Files and scientific plots

- `raw/<session>.csv`: continuous raw EEG and corrected LSL timestamps.
- `sessions/<session>/events.csv`, `answers.csv`, `session.json`: event times, answers/0–2 scores, 1–5 ratings, practice flags, trial order, provenance and session status.
- `stimuli/audio/`: the exact uploaded audio bytes, named by hash.
- `study_setup.json`: saved questions, answer keys and background configuration.
- `reports/<recording>/signals.png` and `signals.pdf`: full-resolution NumPy/Matplotlib waveforms and Welch power spectra.
- `reports/<recording>/recording.npz`: arrays `timestamps` (N,), `eeg` (N,4), `channel_names`, `nominal_sample_rate`. Load with `numpy.load(path, allow_pickle=False)`.
- `reports/<recording>/quality.json`: duration, missing/gap checks and heuristic warnings. `reports/report_errors.json` lists recordings whose reports could not be generated; their original files are still exported.

Raw files are never modified by report generation. Practice answers are retained but flagged. On errors/abort, partial files are preserved. Interrupted sessions are marked on next launch. Close confirmation protects active recording; keep the app open until saving finishes. Do not run two copies of the app simultaneously.

## Study limits

This is research prototype software, not a validated comprehension detector or medical device. Events use the LSL clock; EEG uses inlet clock correction. AUDIO_PLAY_REQUEST / AUDIO_PLAYBACK_RETURNED bracket native `afplay` calls. They do not measure acoustic onset or remove headphone latency. Spectra assume Muse's 256 Hz and use the longest continuous timestamp segment. Graph flags are screening heuristics, not evidence of clean EEG. No live comprehension classifier is included.

Provide appropriately licensed stimuli and reviewed questions; no participant recordings, stimuli or answer keys ship in this repository. Follow your institution's participant/consent requirements. Review signal quality before using recordings as study data.

## Compatibility and release status

Separate build jobs target **Apple Silicon** and **Intel** using Python 3.12. Dependencies set a practical macOS 12+ baseline; built artifacts may require a newer macOS depending on dependency wheels. Confirm the OS versions supported by a particular release in its release notes. No claim of support for every historical Mac is made.

The local Apple Silicon preview uses Python 3.12 and pinned dependencies. Intel and Apple Silicon builds run import, interface-asset, report-generation and HTTP tests in CI. Older macOS versions and real Bluetooth/audio behavior still require hardware checks. Bluetooth, audio output, native folder selection and an entire session must be smoke-tested on each supported architecture before declaring a release stable.

Builds are ad-hoc signed locally, **not Developer ID signed or notarized**. macOS may block downloaded builds. For routine distribution without those warnings, the maintainer must provide an Apple Developer ID and notarize releases. Do not disable Gatekeeper. A source launcher is available below as an alternative.

## Run from source

Install Python 3.12 from python.org, then double-click `Start-From-Source.command`. Its first run creates `.venv` and installs dependencies; subsequent runs are local. Or:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

## Development / Mac packaging

```sh
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -v
python -m PyInstaller --noconfirm NeuroBridge.spec
dist/NeuroBridge.app/Contents/MacOS/NeuroBridge --self-test
ditto -c -k --sequesterRsrc --keepParent dist/NeuroBridge.app NeuroBridge-macOS-preview.zip
```

Build each architecture on a matching Mac. CI (`.github/workflows/macos.yml`) tests and packages both architectures. Push a `v*` tag to create a **prerelease** with downloadable ZIPs after both jobs succeed. Inspect the artifacts and smoke-test before promoting the prerelease. A signing/notarization step is not yet configured.

Repository contains application source and tests only. `.gitignore` excludes environments, builds, recordings and arrays. Before publishing, review `git ls-files` to verify no participant data were added.

## Repository and releases

Source: https://github.com/Astroura/neurobridge

CI builds Intel and Apple Silicon apps. A pushed `v*` tag creates a downloadable prerelease for hardware smoke-testing; the maintainer promotes it after verification. Source code contains no participant data or audio clips.

## Third-party components

MuseLSL (BSD-3-Clause), pylsl/liblsl (MIT), NumPy (BSD), SciPy (BSD), pandas (BSD), Matplotlib (Matplotlib/PSF-derived license), pywebview (BSD) and PyObjC (MIT). Packaged builds collect dependency license files in `third_party_licenses`. Consult each dependency for complete notices. NeuroBridge source has no additional open-source license grant yet; choose one with the project owners before making a public release.
