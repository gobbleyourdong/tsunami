# Manus Infrastructure Map
> Scraped 2026-03-28

## Domains
| Domain | Purpose | Behind |
|--------|---------|--------|
| manus.im | Main webapp (Next.js) | CloudFront |
| api.manus.im | API gateway (ConnectRPC/protobuf) | - |
| wss://api.manus.im | WebSocket (chat, notifications, STT) | - |
| metrics.manus.im | Telemetry | - |
| files.manuscdn.com | CDN (S3 + CloudFront) | CloudFront → S3 |
| manus.space | Published user spaces | Cloudflare (104.18.26/27.246) |
| manus-preview.space | Preview deployments | - |
| manus.computer | E2B sandbox domain | - |
| pages.manus.im | Pages | - |
| cname.manus.space | Custom domain CNAME target | - |
| sentry.prod.ops.butterfly-effect.dev | Error tracking | - |

## Client-Side API Keys (public)
| Service | Key |
|---------|-----|
| Amplitude Analytics | 46ac3f9abb41dd2d17a5785e052bc6d3 |
| Fingerprint.js Pro | nG226lNwQWNTTWzOzKbF |
| Google Drive App ID | 1073362082968-a8ind2sh24p7c41svhvgof1bht9me0eo |
| Google Maps API | AIzaSyDcXHo-1cHpFHPMlBDoMHnvI6r00_XkNKg |
| Intercom | k7n2hgls |
| Cloudflare Turnstile | 0x4AAAAAAA_sd0eRNCinWBgU |
| hCaptcha | 7b4c0ca8-0e48-47b8-82de-6c1a5f7e0e16 |

## Tech Stack
- **Frontend**: Next.js (React), Lit HTML (Space Editor)
- **API Protocol**: ConnectRPC (protobuf over HTTP, not REST)
- **Analytics**: Amplitude + Fingerprint.js Pro + Google Tag Manager
- **Error Tracking**: Sentry
- **Sandbox**: E2B (manus.computer)
- **CDN**: CloudFront → S3
- **Spaces**: Cloudflare (custom domains via CNAME)
- **Canvas**: Konva.js
- **Animations**: Framer Motion
- **Syntax Highlighting**: Shiki
- **Color Picker**: Coloris (Space Editor)
- **Slides**: HTML/CSS → screenshot → PDF/PPTX

## Space Editor (Embedded in every deployed space)
- File: spaceEditor-DPV-_I11.js (~22K lines)
- Framework: Lit HTML (Google's lightweight templating)
- Features: DOM patch system, WYSIWYG text/style editing, undo/history
- Auth: Cookie-based access_token, edit codes
- Tracking: Amplitude + ThumbmarkJS fingerprinting
- Custom Elements: manus-content-root, footer-watermark, lit-popup, lit-dialog

## Environment Variables (client-side)
```js
window.__manus_space_editor_info = {
  spaceId, patchList, hideBadge, sessionId, isWebDev, usageStatus
}
window.__manus__global_env = {
  apiHost: "https://api.manus.im",
  host: "https://manus.im",
  amplitudeKey: "..."
}
```

## Webapp Assets (from homepage)
- 44 JS chunks, 10 CSS files
- Largest: 1.9MB (Konva + Framer Motion + Shiki)
- Protobuf: 800KB (all service definitions)
- PDF Worker: 1.3MB
- FPM Loader: 178KB (Fingerprint Pro)

## robots.txt
Allows: Twitterbot, facebookexternalhit, LinkedInBot, Google bots
Blocks: All other crawlers (User-agent: * / Disallow: /)
