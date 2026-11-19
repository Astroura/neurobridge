# NeuroBridge pilot collection and spectral protocol

Version NB-QC-1. Defined November 19, 2026 for future sessions. These are conservative pilot engineering criteria, not validated physiological cutoffs or a formal preregistration. Do not revise them after viewing understanding scores. Amendments require a new policy version, rationale and date; analyze old and new versions separately.

## Before fitting

Use a quiet room, a supported chair, consistent headphones and comfortable fixed volume. Keep the screen and eyes-open condition the same across subjects. Document subject code, language proficiency, speaker, intended spoken script, passage ID and order. Review each question and its answer key before collection. Obtain the consent required by your study.

Place the Muse 2 forehead sensors against bare skin. Move hair clear of the forehead and the sensors behind both ears. Extend the earpieces gently to a comfortable fit. Follow the manufacturer's cleaning and fitting instructions; a slightly damp cloth on the skin can help contact. Do not soak the device. Check TP9 and TP10 in particular. Avoid adjusting, touching, talking or chewing during the baseline or listening passage. Relax the jaw and blink normally; do not force prolonged blink suppression.

## Live acquisition check

Connect Muse once. If a terminal already owns the Bluetooth connection, the live EEG check can preview its LSL stream; do not open a competing Bluetooth streamer. Choose **Start live EEG check** to see the actual incoming raw traces and channel-specific reasons. This preview stays in RAM; it is not a recording and is not an impedance measurement.

The app requires ten continuous passing seconds across **TP9, AF7, AF8 and TP10** before every trial's baseline. The recent data must be fresh, finite, correctly timed and sampled at 256 Hz. Each two-second block must have exactly 512 samples, increasing timestamps, no gap above 20 ms, and a sample span of 1.98–2.02 seconds. On every channel:

- Peak-to-peak amplitude is at most 200 µV.
- No raw sample has absolute amplitude at least 995 µV.
- Standard deviation is at least 0.1 µV.

These are raw-data checks. The plot retains raw amplitude units and spike extrema. “Passing” means only that these rules pass, not that the signal is artifact-free or that the subject understands the speech. Bluetooth “connected” alone does not pass the check. No fresh samples for 1.5 seconds resets readiness.

If saturation or large repeated excursions persist, stop and refit. Look at all four traces, especially TP9/TP10, rather than trying to make a filtered graph look smooth. Do not increase the threshold to obtain more accepted data. If the gate cannot pass within 120 seconds, the session stops and preserves its partial EEG and events.

## Baseline and trial sequence

Each trial has its own sequence: signal check, **30-second quiet eyes-open baseline**, three-second fixation, listening/live speech, optional questions/rating, five-second rest. The baseline instruction is to look at the cross, sit still and relax the jaw.

Before playback, the raw baseline must contain at least ten accepted nonoverlapping two-second epochs and at least 70% of its complete epochs must pass on all four channels. In a 30-second baseline with 15 complete epochs, that requires **11 passing epochs, or 22 seconds**. A failed baseline is logged and followed by a new fit/stability check and a new baseline. After three failed attempts the session stops. Attempted baselines and raw data remain preserved; only the last accepted baseline is paired with that trial.

For live speech, Start speaking remains unavailable until the recent signal is ready, and the worker verifies readiness again when it receives the command. For audio, playback waits for the recent signal to pass again. Acquisition checks do not guarantee later listening data will pass the offline analysis.

During listening, if the operator sees persistent saturation, stop and keep partial data. Record the interruption. After refitting, use a new reviewed passage where possible; repeating the same passage creates a learning/repetition confound. The software does not silently interrupt or replay a passage when an amplitude excursion occurs.

## Fixed offline eligibility

The raw CSV is never overwritten. The fixed run uses the existing 1–40 Hz zero-phase Butterworth/SOS filtering, no notch, raw 200 µV screening, rail/flat/missing checks, 0.25-second artifact margins and one-second filter-edge guards. Continuous retained segments under three seconds are excluded. No rereferencing, interpolation, resampling, gap filling or automatic channel dropping is performed.

Baseline and listening phases are independently divided into **nonoverlapping two-second epochs anchored to their saved start markers**. The incomplete tail of a phase is not analyzed and is not part of the complete-epoch denominator. Every accepted epoch must pass the same raw checks above and every sample must also pass the existing filtered common four-channel mask. A failed channel rejects the whole epoch across all channels.

A trial qualifies for paired spectral features only if:

1. Its linked baseline has at least **10 accepted epochs (20 seconds)** and **70% acceptance** among complete candidate epochs.
2. Its listening interval has at least **5 accepted epochs (10 seconds)** and **70% acceptance** among complete candidate epochs.
3. It is not a practice trial, uses the matching policy/settings, and has both start/end event pairs.

Clips under ten seconds cannot qualify. A ten-second clip needs all five epochs clean to qualify; longer reviewed passages around 20–30 seconds provide more opportunity to meet the requirement. These duration suggestions are collection choices, not evidence of matched difficulty.

Failure means **excluded/unavailable**, not zero power, zero comprehension or a reason to loosen the rule. Questions and understanding ratings remain recorded even if EEG is excluded. Existing descriptive whole-record plots and powers are separate from the primary eligibility result. Runs using altered thresholds, a notch or manual exclusions do not qualify under this fixed profile.

## Spectral features and statistical units

For each accepted epoch and channel, calculate a Welch periodogram using a Hann window, 512 samples at 256 Hz, nfft 512, constant detrending, density scaling and **no overlap**. Average PSDs across accepted epochs within each phase. Integrate theta 4–8 Hz, alpha 8–13 Hz and beta 13–30 Hz using the same inclusive band edges and trapezoidal integration in both phases. Power units are µV². A complete paired trial produces 12 features: three bands across four channels. The change for each is `10 × log10(listening power / baseline power)`, in dB. Zero/nonpositive denominators yield an unavailable change, not infinity.

The unit is **the trial nested within a participant**, not the individual EEG sample, two-second epoch, overlapping window or channel. Report all prespecified band/channel features rather than selecting whichever appears correlated with scores. Repeated trials from one person remain related. Any future validation split must keep a participant's trials together. This app does not fit a comprehension classifier or run confirmatory significance tests.

Define a hypothesis, primary contrast and sample-size/participant plan separately before confirmatory testing. For now, these features are descriptive pilot measurements. Different passage content, speakers, proficiency, question quality, order and retained data can all affect comparisons.

## Saved audit trail and interpretation

New sessions store the complete policy and its SHA-256 fingerprint before recording. Events identify quality checks, baseline attempts, rejection/acceptance, listening and responses. After saving, the app runs the locked analysis and writes an immutable cleaning run. Review & clean shows trial eligibility and reasons. Exports include `quality_policy.json`, `quality_trials.csv`, the full analysis JSON, raw-source fingerprint and the existing masks/cleaned files. The outcome scores do not enter the quality decisions.

Applying this rule to an old session is explicitly labelled **retrospective exploratory application**. It does not make old data prespecified or repair prior questionnaire items. If automatic analysis fails, the raw recording remains saved and the app reports that analysis is unavailable.

## References

- [Muse 2 fitting and starter guide](https://choosemuse.com/pages/starter-guide-muse-2): sensor contact and fitting. It does not validate these custom thresholds.
- [MNE bad-span/epoch rejection](https://mne.tools/stable/auto_tutorials/preprocessing/20_rejecting_bad_data.html): amplitude/flatness screening and rejection concepts. The numerical NB-QC-1 thresholds and retention minima are project-specific choices.
- [SciPy Welch documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html): PSD estimator and scaling.
