## Live quality checks and fixed spectral protocol (0.6.0)

Session setup now shows raw TP9/AF7/AF8/TP10 traces and channel-specific warnings. Start the live check after connecting Muse. Each trial waits for ten continuous passing seconds and receives its own 30-second quiet baseline. Failed raw baselines are logged and retried, up to three attempts. The packaged-app Muse decoder import is now checked as well as reporting dependencies.

[QUALITY-PROTOCOL.md](QUALITY-PROTOCOL.md) defines NB-QC-1, its numerical criteria and limits. A versioned policy and SHA-256 fingerprint are saved before recording. Primary eligibility requires 70% accepted nonoverlapping 2-second epochs in both phases, at least ten baseline epochs and five listening epochs. The fixed analysis saves paired baseline/listening band powers and dB changes, with one feature set per trial. It never uses answers or understanding scores to choose accepted EEG. Short clips can be recorded but cannot meet the primary-analysis duration rule.

After saving, the locked screen runs automatically. Review & clean displays the primary eligibility reasons separately from descriptive recording-wide powers. `quality_policy.json`, `quality_trials.csv` and full analysis JSON are included in cleaning/workspace exports. Changing the cleaning preset disqualifies that run from the fixed profile. Old-session applications are explicitly retrospective. These are pilot engineering thresholds, not validated artifact detection or a comprehension biomarker.

## Stimulus collections (0.5.1)

Download the [0.5.1 release packs](https://github.com/Astroura/neurobridge/releases/tag/v0.5.1-preview), keep each ZIP zipped, and import from Session setup. English Simple v2 and Arabic Simple v2 each contain six human recordings and two simple English questions per clip. Hindi-English Listening v1 contains four matched content pairs (eight clips) with **no questions, rating or score**. Listening-only trials need app 0.5.1 and have an explicit response mode, never blank placeholder questions.

Google FLEURS source transcripts, licenses, per-file gain, hashes, answer evidence and machine cross-checks are included. [Material review](stimulus-materials/collections/REVIEW.md) states the checks and their limits. These are short pilot recordings, not a validated or difficulty-matched test. Arabic uses formal written passages from source locale ar_eg, not a conversational dialect guarantee. Questions in both question packs require English reading. Select one translation per content ID per participant or counterbalance repetition.

Build with `python scripts/build_stimulus_collections.py`; verify with `python scripts/verify_stimulus_collections.py`. Build-only dependency: soundfile. The committed FLACs are pinned by SHA-256; rebuilding does not fetch remote audio. `answers.csv` adds a trailing `response_mode` column: questionnaire trials keep existing fields, while listening-only rows leave questions, score and rating blank. `RESPONSES_SKIPPED` explicitly marks skipped responses in events.csv.

# NeuroBridge for Mac

Local Muse 2 EEG recording and passage-comprehension experiments.

## For participants and project partners

1. Download the ZIP for your Mac from [Releases](https://github.com/Astroura/neurobridge/releases): **arm64** for Apple Silicon; **x86_64** for Intel. Extract it and move **NeuroBridge.app** to Applications.
2. Open the app. Use **Change folder…** to choose where recordings will be saved. The default is `~/Documents/NeuroBridge Data`. Switching folders does not move existing recordings.
3. Turn on the Muse, close other apps connected to it, and press **Connect Muse**. Allow Bluetooth access when macOS asks. If it was denied, enable NeuroBridge in System Settings → Privacy & Security → Bluetooth and reopen the app.
4. In **Choose your trials**, use **Choose stimulus ZIP…**, keep the download zipped, preview its contents, and select the trials you want. Or add your own audio/live trial. Expand **Edit trial & response settings**. Choose two factual questions with answer keys and a rating, or listening only with no responses. Uncheck trials to exclude them from this session. **Save setup** keeps the full list in the recording folder; **Load saved setup** restores it after relaunch.
5. In **Review & begin**, enter a coded subject ID and review the selected materials and answer keys. The checklist explains any missing fields. Check the review box to enable Start session.
6. Press **Start session**. EEG must arrive before the baseline begins. Practice runs first, followed by randomized experimental clips. Remain silent during listening. The app plays audio through the Mac's selected audio output.
7. After the session, inspect **Recordings & graphs** or choose **PNG/PDF report**. **Export workspace** opens a native folder picker and writes one uniquely named ZIP containing all data from the currently selected recording folder.

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

Provide appropriately licensed stimuli and reviewed questions; no participant recordings ship in this repository. Publicly licensed source stimuli, transcripts and original answer keys for the new pilot collections are included with their review records. Follow your institution's participant/consent requirements. Review signal quality before using recordings as study data.

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

## Live conversation and the downloadable stimulus pack (0.2.0)

Download **NeuroBridge-Stimulus-Pack-v1.zip** from Releases, separately from the app. In Session setup, use **Choose stimulus ZIP…**; preview the contents and choose which trial templates to add. It copies licensed audio into the selected recording folder. It preserves provenance/license files for later data export. Save the setup after editing. The pack includes all six current practice audio clips and three draft stories, each in English and Egyptian Arabic, with matching factual questionnaires. Recorded-trial questions are deliberately blank until someone reviews the audio. This practice collection is not the final validated study corpus; Arabic audio excerpts are consecutive fixed-time segments from one source, and all source/review limitations are included in the pack.

Choose **Add live conversation**, then enter the spoken language/dialect, coded speaker ID, intended script/topic, and either two factual questions/answer keys or listening-only response settings. **Duplicate trial** copies a trial when preparing another language version. Practice and randomization work in both modes. Do not administer both translations of the same content to the same subject without accounting for learning/repetition.

The live session uses the same baseline and fixation as audio trials, then waits for the operator to press **Start speaking**. EEG continues while the operator speaks. **Finish speaking** marks the end. Questionnaire trials reveal two scored factual questions (0–2) and a perceived-understanding rating (1–5); listening-only trials proceed directly to rest with no response prompt. A score of 1/2 is not a measurement of "exactly half understood." The app does not infer comprehension from EEG. Keep question text readable to the subject, and do not reveal answer keys or transcripts during listening.

Live speech is **not microphone-recorded**. `LIVE_SPEECH_START_REQUEST` / `LIVE_SPEECH_END_REQUEST` use the host LSL clock when the operator command arrives; they do not measure acoustic onset. Store script deviations and interruptions in session notes. EEG/answers are linked by participant, session and trial IDs; answer rows now include language, mode and speaker ID. Silent listening should be distinguished from subject speech/movement before analysis.

Pack creation is reproducible from checksum-pinned sources with `scripts/build_stimulus_pack.py`; its extra dependencies are build-only and are not required by the Mac app. CI publishes a separate stimulus-pack ZIP alongside the apps. Maintainers can use **Actions → Test and build Mac apps → Run workflow**, setting `release_tag` to a new preview version; release publication waits for both app tests/builds and stimulus packaging.


## Review & clean (0.4)

Open **Review & clean** from the sidebar or a selected recording. Choose a raw Muse CSV, a peak-to-peak screening threshold (200 µV starting preset), and optionally a 50/60 Hz notch if residual mains noise is present. Add manual exclusions in seconds from the first EEG timestamp for observed blinks, movement, subject speech or headset adjustments. Run the screen, inspect the raw/filtered comparison and retained-data percentages, then download the analysis ZIP. Earlier runs can be reopened from the saved-run selector. Use **Export workspace** to choose a native destination for the full workspace archive, including cleaning results. Raw files are never modified.

The workflow requires approximately 256 Hz EEG with strictly increasing finite timestamps. It splits gaps over 20 ms; detects missing/nonfinite samples, near-rail values (absolute raw amplitude ≥995 µV), 2-second peak-to-peak threshold violations and flat windows (SD <0.1 µV); applies manual intervals and a 0.25-second artifact margin; filters each remaining per-channel span independently with a Butterworth 1–40 Hz SOS filter (SciPy N=4, an eighth-order band-pass) via SciPy `sosfiltfilt` (forward/backward, zero phase, squared magnitude response), optionally preceded by a Q=30 notch. It rejects spans shorter than 3 seconds and trims 1 second from each filtered end. Edge guards reduce transients without proving their absence. No ICA, interpolation, rereferencing, resampling or gap filling occurs. This preset is for exploratory band power, not ERP or slow-potential analysis.

Each immutable run is saved under `cleaned/<run-id>/`: `cleaned.csv`, `cleaned.npz`, `analysis.json`, `rejected_intervals.csv`, `trial_analysis.csv`, `comparison.png`, `comparison.pdf`, and `PROCESSING.txt`. Original timestamps/sample count are retained. CSV blanks and NPZ NaNs mark rejected channel samples. NumPy `eeg` is N×4 in µV; `usable_channel` is N×4, `usable` is the common N-sample mask across all four channels; `reason_bits` is an N×4 rejection mask with the bit legend represented by the interval reasons. Load with `numpy.load(path, allow_pickle=False)` and apply `usable` before four-channel analysis. The JSON includes source SHA-256, dependency versions, thresholds, exclusions and pipeline version. Cleaned arrays are distinct from the raw `reports/recording.npz` export.

Absolute theta (4–8 Hz), alpha (8–13 Hz), and beta (13–30 Hz) powers use common four-channel retained intervals only. Welch PSD uses complete 2-second Hann windows, 50% overlap, constant detrending, and window-count-weighted averaging across contiguous spans without stitching gaps. Band powers integrate the PSD using the trapezoid rule. Raw comparison PSD can cover different intervals than the retained PSD. No estimate is produced without at least two continuous retained seconds. Trial power/retention is available only when linked session playback/operator markers exist; these are not measured acoustic onsets. Retention percentages describe recorded samples, not missing time; sample-derived seconds assume 256 Hz. The app applies no baseline normalization or comprehension classifier.

Screening thresholds are heuristics, not validated EEG acceptance criteria. Low retained coverage, missed artifacts and short spans require review or re-recording. Clipped/missing EEG cannot be reconstructed. A smooth trace does not establish valid brain activity.


## Notebook interface (0.5)

The approved DESIGN.md defines the research-notebook and bench-instrument interface. Setup uses a trial ledger and a narrower workspace/control margin. Recordings and cleaning use labeled SVG figures; teal controls are distinct from violet retained-data annotations. Plex Serif/Sans, the Arabic counterpart, Lucide symbols and their license notices are bundled for offline use. Matplotlib reports and the browser share presentation tokens from `neurobridge/static/theme.json`.

Active capture keeps Stop and the timer visible. During experiment questions, participant view hides operator navigation, notes and paths; use Show operator controls to switch back. Arabic question groups follow their text direction. The scientific pipeline and stored data format are unchanged. See UI-REVIEW.md for viewport/state checks and limits.

### Terminal connection fallback

Choose **Start Muse in Terminal** in Folder and headset. It opens a generated `Start-Muse.command` using the bundled MuseLSL worker with `--backend bleak --lsltime`, matching the original working script. No separate Python installation is needed. Wait for **Streaming EEG**, keep Terminal open, return to NeuroBridge and choose **Start live check**. Inspect all four traces before collecting. Stop recording first, then press **Control+C in Terminal** to disconnect. Closing NeuroBridge does not stop this external Terminal stream. The in-app Disconnect button controls only the in-app worker. Do not run another Muse connection at the same time.
