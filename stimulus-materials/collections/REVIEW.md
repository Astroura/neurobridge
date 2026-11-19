# Stimulus material review, 2026-11-19

## Scope and limits

Twenty complete human recordings: six English question trials, six Arabic question trials, and eight Hindi/English listening-only trials (four paired content IDs). Source: [Google FLEURS](https://huggingface.co/datasets/google/fleurs), pinned revision 70bb2e84b976b7e960aa89f1c648e09c59f894dd, CC BY 4.0. Arabic is labelled by dataset locale ar_eg but the selected passages use formal written Arabic; no conversational-Egyptian claim is made.

Codex proofread all supplied source transcripts, checked each keyed answer against an explicit supporting phrase, reviewed the Hindi/English pair meanings, inspected waveform integrity/levels, and compared every retained clip with independent local Whisper small transcription. Hindi additionally received a Whisper medium cross-check. Machine outputs, disagreements, answer evidence and waveform measurements are preserved in review.json. These checks do not constitute direct listening, a native-speaker review, a standardized language test, matched item difficulty, or scientific validation of comprehension. No direct auditory review was available in this session. Source transcripts were not silently rewritten to match ASR guesses.

All 24 question items are simple factual multiple choice with three options. The app also offers I don't know. Both English and Arabic question packs use English questions, so English reading is required and can affect measured performance. Each answer is stated in the passage; there are no trick questions, inference questions, or answers requiring outside facts. These short 4–15 second clips differ in speaker, duration and topic. Do not compare language scores as if the packs were a controlled matched test. The two questions on the camping clip share evidence and are not independent items.

## Audio and package checks

Complete source utterances were retained, with no mid-sentence cutting, splicing, denoising, dynamic compression, resampling, or synthetic narration. A constant gain targets -24 dBFS RMS but is capped so peak stays at or below -1 dBFS. Each result is mono PCM16 at its original 16 kHz. This is electrical-level adjustment, not LUFS or calibrated perceived/SPL matching. Original downloaded-WAV hashes, processed hashes, gain and levels are recorded. These are rendered source assets; the WAV served by the dataset viewer can differ in container encoding from a dataset's original FLAC.

Every retained output is finite, non-silent and has no full-scale clipped sample. Built ZIPs are checked for readable mono PCM16 WAVs, full duration, unique/checksummed entries, attribution and review files, and successful import plus protocol validation. The app's automated worker checks cover ordinary questionnaires, live listening-only and prerecorded listening-only trials. Listening-only trials produce no QUESTIONS_START or RESPONSES_SAVED event. They write RESPONSES_SKIPPED, and answers.csv has response_mode=none with blank answer, score and rating fields. EEG and playback markers continue normally. Hardware playback and a Muse session with these materials have not been rehearsed here.

## Excluded candidates

- Arabic FLEURS 1662 (alloys): full-scale source peaks; replaced by 1720.
- English FLEURS 1614 (ocelots): independent transcription failed on the animal name used by the proposed item; replaced by 1600.
- Hindi/English 1593 (wheels/rails): Hindi machine transcription disagreed on the spoken year. Pair excluded rather than correcting the transcript by assumption.
- Hindi/English 1555 (churchyard sculptures): English small and medium transcriptions both returned “dust” where the source says “doves”. Pair excluded.

Hindi/English pairs share content IDs 1559, 1526, 1615 and 1594. Select one translation per content ID per subject or explicitly counterbalance repetition. The app randomizes non-practice trials and does not automatically alternate languages. No trials in these packs are marked practice. Use a separate practice trial if your protocol requires one.

## Per-clip proof notes and answer keys

### en_us_1528

Both questions use the explicit family/young-child phrase. They are intentionally easy and partly redundant; do not treat them as independent psychometric items.

1. Who are the camping areas for? **Families**. Source evidence: families with young children
2. Who are the families bringing? **Young children**. Source evidence: young children

### en_us_1531

Both Indian Ocean and eastern coast are explicit. The source clip was quiet; constant gain was applied, with no content change.

1. Which ocean are the islands in? **Indian Ocean**. Source evidence: Indian Ocean
2. Which coast of Africa is mentioned? **Eastern coast**. Source evidence: eastern coast of Africa

### en_us_1541

Machine transcription writes Career for Courier. Questions deliberately target the clearly transcribed delivery speed and spare parts, not the disputed word.

1. How are things delivered? **Quickly**. Source evidence: quickly
2. What can be delivered? **Spare parts**. Source evidence: spare parts

### en_us_1521

In space and back down are explicit. Questions test the passage wording; this is not an assertion that every telephone call uses a satellite.

1. Where is the satellite? **In space**. Source evidence: in space
2. Where does it reflect the call? **Back down**. Source evidence: back down

### en_us_1522

Virtual field trips and staying with the class are explicit. A minor ASR connector difference does not change either answer.

1. What kind of field trips are mentioned? **Virtual trips**. Source evidence: virtual field trips
2. Where do the students stay? **With their class**. Source evidence: sitting with their class

### en_us_1600

Fishing and visiting parks are explicit items in the activity list. Distractors are absent from the passage.

1. Which activity is mentioned? **Fishing**. Source evidence: fishing
2. What places can people visit? **Parks**. Source evidence: visiting parks

### en_us_1559

Hindi and English both say Italian pronunciation is comparatively easy because spelling and pronunciation generally agree. Listening only; no scored items.

Listening only. No question, rating or score.

### en_us_1526

Both languages describe polar night in winter and the Sun not rising above the horizon. Listening only.

Listening only. No question, rating or score.

### en_us_1615

Both languages refer to Aristarchus and the Solar System moving around the Sun. ASR does not reliably spell the proper name; it is retained in the source transcript, not silently replaced. Listening only.

Listening only. No question, rating or score.

### en_us_1594

Both languages mention elephants/giraffes approaching cars and viewing equipment. Listening only.

Listening only. No question, rating or score.

### ar_eg_1942

Clothes and most food coming from plants are explicit. Source text proofread; ASR has spelling errors in the word meaning most. No inference about unmentioned materials is required.

1. What do people make clothes from? **Plants**. Source evidence: ملابسنا من النباتات
2. Where does most of our food come from? **Plants**. Source evidence: معظم الطعام الذي نتناوله من النباتات

### ar_eg_1680

Tiger and swimming are explicit. Avoided the more difficult five-times-strength detail. Arabic orthographic variants in machine transcription are retained in the audit.

1. Which animal is described? **A tiger**. Source evidence: للنّمر
2. What can the tiger do? **Swim**. Source evidence: السّباحة

### ar_eg_1714

Rocket and telescopes are explicit. Avoided asking for an explanation of atmospheric distortion.

1. What carried the satellite into space? **A rocket**. Source evidence: بواسطة صاروخ
2. What do scientists use in space? **Telescopes**. Source evidence: التلسكوبات في الفضاء

### ar_eg_1778

White and factory are explicit. Each question asks for a single concrete noun or color.

1. What color is the smoke? **White**. Source evidence: دخاناً أبيض
2. Where is the smoke coming from? **A factory**. Source evidence: من المصنع

### ar_eg_1737

Lions and large groups are explicit. No question depends on translating the collective-noun term.

1. Which animals are described? **Lions**. Source evidence: الأسود
2. How do they live? **In large groups**. Source evidence: مجموعات كبيرة

### ar_eg_1720

Hot chocolate and expensive fruit juice are explicit. Avoided the less useful Belgian-standards reference.

1. Which hot drink is mentioned? **Chocolate**. Source evidence: الشوكولاتة الساخنة
2. How are the fruit juices described? **Expensive**. Source evidence: باهظة الثمن

### hi_in_1559

Medium-model cross-check supports the source comparative-ease/spelling meaning; small-model negation was inconsistent. Source script retained. Not an auditory certification.

Listening only. No question, rating or score.

### hi_in_1526

Medium-model cross-check supports winter, Arctic/Antarctic and Sun-not-rising meaning, with phonetic/spelling errors in place names and horizon. Source script retained.

Listening only. No question, rating or score.

### hi_in_1615

Medium-model cross-check supports the Solar System revolving around the Sun. Proper name is uncertain in ASR and remains the source spelling. No comprehension score collected.

Listening only. No question, rating or score.

### hi_in_1594

Medium-model cross-check supports animals approaching cars. ASR spells giraffe phonetically. Source script and pair meaning retained.

Listening only. No question, rating or score.

