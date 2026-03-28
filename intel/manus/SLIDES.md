# Manus Slide Generation System
> From direct Manus output, 2026-03-28

## Two Generation Modes

### HTML Mode (Default, 90% of usage)
- Generates slides using HTML, CSS, JavaScript
- Charts via Chart.js
- Text in editable text boxes (separate from background)
- Fully editable when exported to PPTX
- Granular CSS control (fonts, colors, alignment, padding)
- **This is what we should replicate**

### Image Mode
- Each slide = single AI-generated image
- Text baked into the image (non-editable)
- Prompted with slide content as image description
- Artistic/stylized but zero editability
- Text rendering can be imperfect

## Workflow (4 Phases)

### Phase 1: Research
- Web searches, document reading, data analysis
- Asset preparation (generate images, write Python scripts for charts)

### Phase 2: Content Outline
- Markdown file with structured outline
- Per-slide: title, bullet points, speaker notes, visual cues

### Phase 3: Slide Generation
- Dedicated "slides tool" in agent toolset
- Input: Markdown outline file + slide count + generate_mode (HTML|Image)
- Rendering engine processes outline into slides

### Phase 4: Export
- Frontend presentation viewer
- Export to PDF or PPTX
- Backend utility: `manus-export-slides` (programmatic conversion)

## Protobuf Evidence
```
SessionService:
  ListSlideTemplates
  GetSlideTemplateStatus
  DeleteSlideTemplate
  RenameSlideTemplate
  GenerateDocumentSuggestion
  WebPageScreenShotFullPage  ← screenshot for slide images
```

## Key Insight: No Pre-Built Templates
Manus explicitly states: "No static library of pre-designed templates."
Layouts generated dynamically per slide based on content.
Acts like "a web developer building a custom layout for each slide."

## Implementation Path for TSUNAMI
1. Create a slide CSS template (dark-edu-slides.css) — 16:9 aspect ratio
2. Agent generates HTML slides with the template
3. Playwright/wkhtmltoimage screenshots each slide
4. Stitch into PDF or wrap in PPTX using python-pptx
5. All pieces exist: TSUNAMI generates HTML, we have templates, DGX has headless Chrome
