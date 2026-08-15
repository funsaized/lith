# Tech-Image Pipeline — Teknium-style Visual Generation System

A repeatable pipeline for producing Teknium-style announcement graphics, technical infographics, and short motion clips for tech content (full-stack engineering, AI/MLOps, developer tooling).

This document is the result of a deep visual analysis of 22 reference posts (20 images + 2 videos) from @Teknium and @sora_biz, with the captions and target audience in mind. Everything below is grounded in what was actually observed in those references, not generic AI-art advice.

---

## 1. What the references actually look like

The 22 reference posts cluster into **seven clear style families**, not one consistent aesthetic. Teknium's brand is *visual variety inside a strict engineer's signature*: confident typography, deliberate composition, and a willingness to commit to a full aesthetic (manga tape-insert, woodcut, art-deco, neon blueprint, etc.) instead of generic "tech stock." This is the model's most distinctive pattern.

### Style family index (with example post IDs)

| # | Style family | Example refs | Best for |
|---|---|---|---|
| A | **Sticker / Whisper-joke infographic** — multi-panel comic, neon colors, oversized text, "POV:" hook | 2088488, 2087947, 2087686, 2086558 | Quick reactions, "we shipped a thing" announcements |
| B | **Sci-fi brutalist UI** — black tie-fighter panel, big monospaced HUD text, 72px+ HEADLINE, 1-pixel cyan accents | 2087986, 2086568, 2085777, 2085761 | Feature flagships, capability reveals |
| C | **Vintage technical manual / patent diagram** — sepia paper, fine line-drawing, blueprint numbering, callouts | 2087947, 2087686, 2082339 (one panel) | "How it works" educational posts |
| D | **Manga tape-insert / risograph** — bright flat color circles, hand-drawn arrows, screen-tone shading, "episode title" kerned text | 2083232 stills, 2082339 (one panel) | Release announcements, "chapter" framing |
| E | **Editorial screenshot polish** — actual Hermes UI cropped, glossy with purple→blue gradient frames, sticker burst | 2085156 stills, 2084065, 2080502 | Product UI demos |
| F | **Woodcut / analog engraving** — black on cream, hand-etched lines, skull/cog/sigil iconography | 2081450 (one panel), 2081099 | Sponsor/SaaS satellite announcements, "memo from the team" |
| G | **Role-log / status dashboard** — glowing list, low-saturation darks, blinking cursors, log entries | 2084065, 2080502, 2080691 | Operational posts, "we hit X" stats |

Two of the posts are mixed (3+ style families stapled together), which is the *signature move* — see 2082339 (4-panel meme deck) and 2081450 (4-panel comic strip). The takeaway: **don't pick one style, run a 3–4 style rotation per post and let the variety be the brand.**

### Brand DNA (what is consistent across all 22)

Even when the styles vary wildly, the underlying signals are constant:

- **Black or near-black backgrounds dominate** (deep navy `#0A0E1A`, ink black `#000000`, midnight teal `#06141F`). About 70% of refs.
- **Maximum 3 accent colors per image**, always in the same family: hot magenta/pink, cyan, acid yellow, or rust orange. Never rainbow.
- **Oversized typography** — headlines are 8–15% of frame height. Body text is monospaced or chalkboard serif.
- **One subject, one idea** — every image is a single declarative statement. No infographics with 8 bullet points.
- **Posters, not slides** — readable from a thumbnail, designed to be re-pinned.
- **Hand-drawn energy** — even the most "polished" images (sci-fi brutalist) have asymmetric composition, off-center alignment, or a single decorative flourish.
- **Iconography vocabulary** — lightning bolts, sparkles, skulls, magnifying glasses, telescopes, gears, cogs, concentric circles, "1Q" / "Chapter" / "Issue 001" framing devices, mock newspaper mastheads.

---

## 2. Pipeline architecture

```
                    ┌─────────────────────────────────────────────────────┐
                    │                  1. INGEST                         │
                    │   topic brief + post copy + style pick + aspect     │
                    └──────────────────────┬──────────────────────────────┘
                                           │
                                           ▼
                    ┌─────────────────────────────────────────────────────┐
                    │              2. STYLE BIBLE BUILDER                │
                    │   pull relevant style guide + pose prompt + tokens │
                    └──────────────────────┬──────────────────────────────┘
                                           │
                                           ▼
                    ┌─────────────────────────────────────────────────────┐
                    │              3. DRAFT GENERATION                   │
                    │   parallel gen: GROK (primary) + OPENAI + MINIMAX  │
                    │   N=4-8 candidates per request                     │
                    └──────────────────────┬──────────────────────────────┘
                                           │
                                           ▼
                    ┌─────────────────────────────────────────────────────┐
                    │              4. SCORING & RANKING                  │
                    │   CLIP/visual + brand-DNA check + readability     │
                    └──────────────────────┬──────────────────────────────┘
                                           │
                                           ▼
                    ┌─────────────────────────────────────────────────────┐
                    │              5. POST-PROCESSING                   │
                    │   typography overlay, crop, color-grade, export   │
                    └──────────────────────┬──────────────────────────────┘
                                           │
                                           ▼
                    ┌─────────────────────────────────────────────────────┐
                    │              6. REVIEW & UPLOAD                    │
                    │   human approve → xurl media upload → post        │
                    └─────────────────────────────────────────────────────┘
```

### Model routing (the only three you have)

| Model family | When to use | Why |
|---|---|---|
| **Grok (xAI Imagine)** — `grok-imagine-image-quality` for stills, `grok-imagine-video-1.5` for video | **Primary workhorse.** 70% of generation. | Best at the "weird style that nobody else can do" — manga tape-insert, art deco, woodcut, neon brutalist. Image-editing is supported (image-to-image) so you can lock a style reference and re-render. Video is image-to-video only and 1–15 s — perfect for the 6–8 s clips Teknium uses. |
| **OpenAI (gpt-image-1 / DALL-E)** | **Polish + integration.** 20% of generation. | Better at coherent typography inside the image (the "Reuters headline" bug than Grok has). Use OpenAI for **editorial screenshot polish** (family E) and any post where readable text inside the image is non-negotiable. |
| **MiniMax** | **Cheap variation & backgrounds.** 10% of generation. | Use for background-pattern generators, sticker illustrations, and "throwaway" variation rounds. Also good at vector-flat sticker style. |

**Rule of thumb:** Grok first, OpenAI second, MiniMax third. Always run at least 4 candidates per generation call — the hit rate is dramatically lower than builders expect.

---

## 3. The seven style recipes

Each style family maps to a concrete prompt template. Drop these into `templates/` and render the parameterized version per post.

### A. Sticker / Whisper-joke infographic

```
[FRAME]
Sticker-sheet composition, 4-6 hand-cut sticker-style shapes on a black
background (#050505). Each sticker is a brightly colored flat 2D shape
(circle, rounded rectangle, badge) with a single phrase or icon.
Decorative elements: hand-drawn arrows, sparkles, comic-book "POW"/"WOAH"
bursts, sweat drops, eye-searing neon outlines.

[TYPOGRAPHY]
Giant sans-serif all-caps HEADLINE at 12% of frame height (Helvetica Neue
Black or similar). Sub-text in handwritten marker font at 3% of frame.

[PALETTE]
Black background, one accent from [hot magenta #FF2E88 | cyan #00E5FF |
acid yellow #F2FF00 | rust #FF6B35]. White reverses for text.

[MOOD]
Tweetable, memetic, reactions-driven. Looks like a sticker pack someone
would sticker-bomb a laptop with.
```

**Best for:** "we shipped a thing," low-stakes announcements, "POV: you tried X" jokes.

### B. Sci-fi brutalist UI

```
[FRAME]
Single black panel, 1920x1080, 16:9. Center-aligned massive HUD-style
text. Background: pure black #000000 with a 1px cyan grid line at 8%
opacity. Optional: a single render of a Tie-fighter, Saturn V, or
geodesic dome as a subtle silhouette at 20% opacity bottom-right.

[TYPOGRAPHY]
Top 1/3: 180px monospaced all-caps headline (JetBrains Mono Bold or
Space Mono Bold) in white. Bottom 2/3: monospaced technical subtext
in cyan #00E5FF at 24px, justified-left, with red #FF3030 inline
emphasis markers like [SYSTEM] or [NEW].

[PALETTE]
#000000 base, #00E5FF cyan accents, #FFFFFF white text, #FF3030 red
for callouts. NO gradients. NO drop shadows.

[MOOD]
Hacker terminal, mission control, "your keyboard is also a weapon."
```

**Best for:** Feature flagships, capability reveals, "we now do X" claims. Most Instagram-friendly of the seven.

### C. Vintage technical manual / patent diagram

```
[FRAME]
Sepia paper background (#E8DCC4), fine ink-line drawing in #1A1A1A.
Centered technical illustration of [SUBJECT — a tool, a rocket, a
gauge, a hand holding a wrench]. Border: thin double-rule with
ornate corner ornaments (fleurons, sunbursts). Blue or red ink
highlights for arrows, measurements, callouts.

[TYPOGRAPHY]
Top: small all-caps "TECHNICAL MANUAL — VOLUME [N]" in serif
(Times, Caslon). Bottom: 2-3 numbered callouts in the same serif
pointing into the diagram with thin lines. Patent-style "FIG. 1"
labels.

[PALETTE]
#E8DCC4 paper, #1A1A1A ink, #C2410C red-orange, #1E40AF blue
accents. Aged feel — slight grain, vignette, light tea-stain
discoloration near corners.

[MOOD]
NASA 1962, an Edwardian engineer's notebook, a steampunk patent
attorney's filing cabinet.
```

**Best for:** "How it works" posts, educational threads, anything that benefits from "we engineered this."

### D. Manga tape-insert / risograph

```
[FRAME]
Single bold flat-color background (one of: #FFD700 yellow, #FF2E88
pink, #00E5FF cyan). Centered hand-drawn illustration in thick
manga-line style (5-8px outlines, flat fills, no gradients).
Screen-tone dots for shading. Single dramatic character/figure
or icon.

[TYPOGRAPHY]
Top: massive display text in chunky display font (Cooper Black or
Hipstería), 200px+, slightly rotated (-2° to +2°). Bottom: subtitle
in same font, half-size. Speech-bubble or thought-bubble for
emphasis.

[PALETTE]
One base color, one black, one or two accent colors. Risograph
overprint effect — slight registration offset where colors overlap
(2-3px shift).

[MOOD]
Bangers, manga chapter titles, a T-shirt you would buy without
hesitation.
```

**Best for:** Release announcements, "chapter" framing, viral moments. Best for IG/TikTok stills.

### E. Editorial screenshot polish

```
[FRAME]
Centered product screenshot (Hermes UI, terminal, Slack, etc.) on a
deep gradient background (#1A0B2E → #2D1B69 → #0F172A). Optional
radial vignette glow behind the screenshot in electric purple
#7C3AED at 30% opacity.

[TYPOGRAPHY]
Top: large headline in Inter Bold or SF Pro Display, white. Each
screenshot bordered with a 2px white outline at 10% opacity and a
48px corner-radius. Subtle reflection drop-shadow below.

[PALETTE]
#1A0B2E → #0F172A gradient, #7C3AED purple glow, white text. The
screenshot itself provides the accent colors.

[MOOD]
App Store feature graphic, Apple keynote slide, a product launch
on the front page of The Verge.
```

**Best for:** UI demos, product launches, "see what we built" posts. **Pair with a real video clip** (image-to-video the same composition for 4–6 s of motion).

### F. Woodcut / analog engraving

```
[FRAME]
Cream paper background (#F4ECD8) with subtle deckle edge. Single
black-on-cream illustration in the style of a 19th-century
engraving: cross-hatched shading, fine parallel lines, bold
silhouette. Subject: a skull, a hand holding a quill, a gear, a
newspaper masthead, an old-timey printing press.

[TYPOGRAPHY]
Top: "BROADSIDE" or "BULLETIN" or "MEMO" in heavy serif
(Bodoni, Caslon). Body text in old-style serif (Garamond) justified
to a single column. Drop-cap on the first letter.

[PALETTE]
#F4ECD8 cream, #1A1A1A black, occasional #8B2A1F blood-red ink for
emphasis. No other colors.

[MOOD]
Pirate broadside, 1880s newspaper, a manifesto from a candlelit
workshop.
```

**Best for:** Sponsor/SaaS partner announcements, "memo from the team" posts, anything where you want gravitas.

### G. Role-log / status dashboard

```
[FRAME]
Dark background (#0A0E1A or #06141F). Centered "terminal" panel
with rounded corners and subtle glow. Inside: monospaced log lines
with timestamps, agent IDs, status badges (✓/✗), low-saturation
status colors. One line in the middle is highlighted (rendered as
a "successful" event) with a soft cyan glow.

[TYPOGRAPHY]
JetBrains Mono Regular at 18-22px. Logger-style timestamps in
#6B7280, agent IDs in #9CA3AF, log messages in #E5E7EB, success
highlights in #10B981.

[PALETTE]
Dark blue-gray background, near-monochrome text. One accent color
(usually cyan or green) reserved for "this is the moment."

[MOOD]
Datadog, a Vercel deploy log, a Sentry incident summary.
```

**Best for:** Operational posts, "we hit X" stats, "in production" announcements.

---

## 4. The non-negotiable prompt anatomy

Every generation — regardless of family — must include these six slots. Fill them in this order; don't skip the framework slots.

```
[FRAME]      aspect, composition, camera/vantage, foreground/background
[PALETTE]    2-4 colors with hex codes; one accent per image
[TYPO]       font + size + weight + color, headline vs body distinction
[ICON]       one or two named motifs/skills/glyphs (lightning, skull, gear)
[COPY]       any literal text that must appear in the image (use sparingly)
[MOOD]       one sentence: who is this for, what is the feeling
```

**Critical rules learned from the references:**

1. **Headline text inside the image is ALWAYS in the same font as the post's typographic intent** — never let the model invent its own font. Specify "display sans-serif, Helvetica Neue Black, 180px" or "Bodoni, 200px, all caps."
2. **Most powerful image-text in a Teknium-style post is 1–3 words.** Examples: "The Crew," "New in Hermes," "1Q," "Just /run." Anything longer is a caption, not a headline.
3. **Specifying hex codes beats describing colors.** "Hot magenta" produces different results across runs; "#FF2E88" is stable.
4. **The decorative element is the brand.** Commit to one signature flourish per image: a lightning bolt, a spark, a magnifying glass, a sunburst, a single ornamental rule. Don't sprinkle five different decorations.
5. **Asymmetric composition wins.** Teknium almost never centers everything. Offset the headline left, place the icon right, draw a connecting flourish. Off-center is on-brand.
6. **One image, one idea.** If you have two ideas, make two images. Don't make a 4-panel when two truths would do — except in family D (manga tape-insert) where panels are the whole point.

---

## 5. The full pipeline, end-to-end

> **Design target only:** This section describes the intended full pipeline; see §7 for what runs today and §9 for implementation status.

### Step 1 — Brief
For each post, run this intake:

```markdown
TOPIC:        [one sentence — what is the announcement]
STYLE:        [A | B | C | D | E | F | G — pick one, or list 2-3 for a strip]
ASPECT:       [16:9 | 4:5 | 1:1 | 9:16]
HEADLINE:     [≤ 3 words shown IN the image]
COPY:         [the rest of the post that goes in the caption, not the image]
ICON:         [one motif: lightning, skull, gear, telescope, magnifying glass, etc.]
PALETTE:      [pick one of the seven family palettes]
MOOD:         [one sentence]
```

### Step 2 — Generate

Run the prompt against Grok first (4 candidates, 16:9 landscape unless post is mobile-first). If Grok fails typography or composition, fall back to OpenAI. Use MiniMax for sticker/background variants only.

```python
# pseudo-code for the orchestrator
def generate(brief):
    candidates = []
    for i in range(4):
        prompt = render_template(brief.style, brief)
        img = grok_image_gen(prompt, n=1, seed=brief.seed + i)
        candidates.append(img)
    # optional: 1-2 OpenAI variants if Grok hit rate is low
    if needs_polish(brief):
        for i in range(2):
            candidates.append(openai_image_gen(prompt, n=1))
    return candidates
```

### Step 3 — Score

Every candidate is scored on three axes (1–5):

- **Brand-DNA**: black background? oversize type? one accent color? off-center composition?
- **Readability**: headline legible at thumbnail size? no Lorem-ipsum gibberish in the image?
- **Concept fit**: does the icon match the topic? does the mood match the post?

Pick the top 1. If the top is < 4 on any axis, run another generation pass with stricter constraints.

### Step 4 — Post-process

Even after generation, almost every Teknium-style image benefits from a finish pass:

1. **Typography overlay** — render the headline in your own font (Inter Black, JetBrains Mono Bold, or Cooper Black) on top of the generated image. This gives you pixel-perfect text without model hallucination. Use Pillow or ImageMagick.
2. **Color grading** — push blacks slightly toward #0A0E1A (not pure black), add a 2px inner border in cyan or magenta, apply a 4% noise/grain layer.
3. **Crop to aspect** — final export at 1920x1080 (16:9), 1080x1350 (4:5 IG), or 1080x1080 (1:1).
4. **Watermark** — small "Hermes" or "@yourhandle" mark in the bottom-right in 1% opacity white. Optional.

### Step 5 — Video (optional)

For posts that need motion (Teknium uses video ~10% of the time):

1. Take the final image as the keyframe.
2. Pass to `grok-imagine-video-1.5` with motion prompt: "subtle parallax, slow zoom in, gentle particle motion, 5 seconds, 1080x1080."
3. Optionally: a 2-second-loop "GIF-style" effect — repeat the same 4-second clip with a 1-frame offset for a lo-fi texture. Teknium's 2083232 video is exactly this aesthetic.

### Step 6 — Approve and post

Use the `xurl` skill for the actual upload. Sequence:

```bash
# Edit media
xurl media upload outputs/post_001_final.png --media-type image/png --category tweet_image

# Stage caption in a file (never in a long shell arg)
echo "Your caption here" > /tmp/caption.txt

# Post via xurl (does NOT auto-post — please confirm before publishing)
xurl post "$(cat /tmp/caption.txt)" --media-id MEDIA_ID
```

---

## 6. Style-family rotation schedule

To keep the feed visually interesting without being chaotic, use this rotation across a week:

| Day | Family | Why |
|---|---|---|
| Mon | A — Sticker | Loud, memetic, week-start energy |
| Tue | B — Sci-fi brutalist | Productive, engineer-flagship |
| Wed | C — Vintage manual | Educational, "how it works" |
| Thu | D — Manga tape-insert | Vibrant, viral-leaning |
| Fri | E — Editorial screenshot | Product UI demo |
| Sat | F — Woodcut | Gravitas, sponsor, "memo" |
| Sun | G — Role-log | Quiet operational post, build-in-public |

Once a week, do a **family mash-up** (e.g., 2082339: 4-panel meme deck combining A + C + D + F in one image). This signals "we are deliberately creative" and is the highest-engagement pattern in the references.

---

## 7. Quick-start (what runs today)

The Python side renders the prompt and overlays typography. The model call
and candidate selection are made by a Hermes session or by hand.

```bash
# 1. Render the prompt + plan
PYTHONPATH=. python scripts/generate.py \
  --topic "Hermes Agent now supports 32 new languages" \
  --style B --aspect 16:9 --headline "32 LANGS" --icon "globe"

# 2. (Hermes session) call image_generate with the printed prompt.
#    Save the returned URL.

# 3. Overlay literal copy and write final PNG
PYTHONPATH=. python scripts/run.py --recipe recipes/live_test_recipe.json \
  --image-url <url-from-step-2> \
  --line SYSTEM='32 language runtimes online' \
  --line NEW='Full-stack · AI · MLOps' \
  --line READY='One agent. Every stack.'
```

Output: `outputs/B_brutalist_32_langs.png`.

For local debug or smoke testing, replace `--image-url` with `--image-file <path>`.

Dry mode (no image source) prints the rendered plan and exits 0 — safe to run before the model call has been made.

---

## 8. Pitfalls learned from the references

1. **Don't let the model pick the style.** Teknium's posts are wildly different from each other because the *creator* is choosing the aesthetic, not the model. If you ask Grok for "a tech announcement graphic," you get generic SaaS stock. Pre-commit to a family.
2. **Type-in-image is the failure mode.** ~30% of the references have deliberate text inside the image that was clearly composed in post-production (the typography overlay). Don't trust the model to render "Hermes Agent" correctly — overlay it in your own font.
3. **Hands, faces, and specific tool logos are unreliable.** Teknium's references don't rely on photorealism — they're all illustration or screen-grab. Push generation toward illustration, never toward photoreal people.
4. **Avoid the "AI gradient" trap.** If the result has a purple-to-blue diagonal gradient, a 3D-rendered icon, and gloss highlight — you've drifted to generic AI imagery. Reject and re-prompt.
5. **Variety is the brand.** If the last 5 posts used the same template, the audience will tune out. Rotate families weekly; use the 4-panel mash-up once a month.
6. **The captions matter as much as the image.** Teknium's captions are short, technical, dry, and forward-looking. No "excited to announce" boilerplate. The image should feel like the visual essay of an engineer, not a launch announcement.

---

## 9. Roadmap

| Stage | Status | Owner |
|---|---|---|
| Prompt rendering from styles.json | done | library |
| ImageMagick typography overlay | done | library (shells to `overlay_text.py`) |
| Recipe loader + driver (`run.py`) | done | library |
| In-repo SKILL.md | done | docs |
| Real `image_generate` call from driver | not done | operator/Hermes |
| Topic-expansion helper (`expand_brief`) | done (library only) | library |
| Post → brief ingestion (URL or scraped post → brief) | **adjacent project, not v1** | future |
| Video augmentation | **out of scope for v1** — see risks below | — |
| CLIP-based candidate scoring | not done | future |
| Aspect-aware overlay masks | not done | future |
| Calendar rotation tool | not done | future |

**Why video is out of v1:** image-to-video models warp small monospaced glyphs (the [SYSTEM]/[NEW]/[READY] overlay at 25pt Menlo) under any motion prompt. Adding video safely requires choosing between (a) overlaying after the video pass, (b) replacing the Menlo+magick path with ffmpeg drawtext, or (c) compositing the still-overlay PNG over each video frame. Each is a separate design decision; deferred.

**Why post → brief is out of v1:** this pipeline writes outward (model APIs, filesystem); post → brief ingestion reads inward (untrusted URLs, scraped content). Different trust boundary, different error budget, different invariant (the source post vs. the literal copy). It's a real plan task — HTML/OG scraping, relevance check, "riff on this" prompt — that deserves its own project, not a roadmap row.
