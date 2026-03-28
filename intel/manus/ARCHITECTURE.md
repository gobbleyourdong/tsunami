# Manus Intelligence Report
> Scraped 2026-03-28 from manuscdn.com and manus.im

## Architecture Overview
- **Frontend**: Next.js app served from `files.manuscdn.com/webapp/_next/static/`
- **API**: ConnectRPC (protobuf over HTTP) at `api.manus.im`
- **WebSocket**: `wss://api.manus.im` for chat, notifications, speech-to-text
- **CDN**: CloudFront → S3 at `files.manuscdn.com`
- **Error Tracking**: Sentry at `sentry.prod.ops.butterfly-effect.dev`
- **Metrics**: `metrics.manus.im`
- **Sandbox**: `manus.computer` domain

## Domains
| Domain | Purpose |
|--------|---------|
| `manus.im` | Main webapp |
| `api.manus.im` | API gateway |
| `metrics.manus.im` | Telemetry |
| `files.manuscdn.com` | CDN (S3 + CloudFront) |
| `manus.space` | Published spaces |
| `manus-preview.space` | Preview deployments |
| `manus.computer` | Sandbox domain |
| `pages.manus.im` | Pages |
| `cname.manus.space` | Custom domain CNAME |

## Third-Party Services
| Service | Key/ID |
|---------|--------|
| Amplitude Analytics | `46ac3f9abb41dd2d17a5785e052bc6d3` |
| Fingerprint.js Pro | `nG226lNwQWNTTWzOzKbF` |
| Google Drive App | `1073362082968-a8ind2sh24p7c41svhvgof1bht9me0eo` |
| Google Maps API | `AIzaSyDcXHo-1cHpFHPMlBDoMHnvI6r00_XkNKg` |
| Intercom | `k7n2hgls` |
| Cloudflare Turnstile | `0x4AAAAAAA_sd0eRNCinWBgU` |
| hCaptcha | `7b4c0ca8-0e48-47b8-82de-6c1a5f7e0e16` |

## Custom Domain IPs
- `104.18.26.246`
- `104.18.27.246`

## Protobuf Services (Complete)

### SessionService (session.v1)
- GetSession, SearchSession, ListSessions, ListSessionsV2
- GetSubtaskList, SearchSessions, UpdateReadPosition
- FavoriteSession, UnfavoriteSession, UpdateSession, DeleteSession
- ShareSession, UnshareSession, SessionFeedback, GetTaskQueueInfo
- ListRecommendUsecases, ShareSessionToCommunity, UnshareSessionFromCommunity
- CreateScheduledTask, ListScheduledTasks, UpdateScheduledTask, DeleteScheduledTask
- GetCompletedScheduledSessions, GetScheduledTaskStatus, ListScheduledTasksWithSessions
- ListSessionsByScheduledTask, Search, ListSlideTemplates, GetSlideTemplateStatus
- ListSessionTemplates, ListSessionFileVersions, GenerateDocumentSuggestion
- CreateFigmaParseTask, LoopFigmaParseTask, DeleteSlideTemplate, RenameSlideTemplate
- PageGetReceivedEmail, GetReceivedEmailDetail, CheckHaveNoneReadEmail
- WebPageScreenShotFullPage, SubmitSessionResponseFeedback

### SessionCollaborateService
- ListCollaborators, CheckAlphaByEmail, SendViewEmail
- InviteCollaborator, RemoveCollaborator, UpdateCollaboratorPermission
- AcceptInvite, RejectInvite, ExitCollaboration
- MemberRequest, GetMemberRequestStatus, ProcessRequest
- JoinSessionCollaborationForTeam

### TeamManagementService
- CreateTeam, UpdateTeamInfo, BatchInviteUser, DismissTeam
- TransferTeam, BatchRemoveMember, UpdateMemberRole
- UpdateTeamStep, UpdateInviteRole, UpdateTeamDeductionSetting
- UpdateTeamPurchaseSetting, BatchDeactivateTeamMembers
- ActiveTeamMember, CreateApiCredential, ListApiCredentials, DeleteApiCredential

### TeamAssetService
- SetTeamSessionAccess, SetTeamAssetControl
- ListTeamAssetControl, ListTeamAssetControlAuditLog
- ListTeamAssetShare, UpdateTeamAssetShare
- ListTeamAssetAuditLog, ListTeamAssetAuditLogByShareUID

### CanvasService (session.v1)
- UpsertCanvas, UpsertCanvasS3, GetCanvas, DeleteCanvas
- BatchUpsertCanvas, Upscale, GetUpscaleResult
- RemoveBackground, GetRemoveBackgroundResult

### ImageService (bizimage.v1)
- OCR, GenerateImage, MarkGenerateImage

### SpaceService / SpacePublicService / SpaceAdminService
- SetSpaceStatus, GetSpaceStatus, PageGetUserSpaces
- EditSpaceSubDomain, GetEditSpaceSiteCode, HasSpaceEditPermission
- SaveSpaceSiteRawData, RestoreOriginalSite
- GetSpaceDetail, GetEditSpaceSiteToken
- BlockSpace, UnblockSpace, AuditSpaceSubDomain

### SubscriptionService
- Query, Update, Preview, Checkout
- TeamSubscriptionCheckout, TeamSubscriptionUpdate, TeamSubscriptionPreview
- Cancel, Resume, BillingPage, LoopTeamUpgradeStatus

### UserService / UserPublicService / UserAdminService
- UserInfo, CheckInvitationCode, UpdateUserProfile
- CreateQuestionnaire, GetFreeQuota, GetAvailableCredits
- GetPersonalInvitationCodes, SetUserInterests
- GetConnectAPP, DisconnectAPP
- GetGoogleDriveAuthUrl, GetOneDrivePersonalAuthUrl
- SendPhoneVerificationCode, BindPhoneTrait
- InExperimentGroup, CheckActivityQuestionnairePermission

### KnowledgeService / KnowledgeAdminService
- ListKnowledge, CreateKnowledge, UpdateKnowledge, DeleteKnowledge
- ListKnowledgeEvents, UpdateKnowledgeEventStatus
- GetKnowledgeDetail, GetBuiltinKnowledge

### ApiProxyService / ApiProxyAdminService
- CallApi, CreateApi, UpdateApi, DeleteApi, GetApi, ListApi

### NotificationService / NotifierService
- GetNotificationList, GetNotificationListV2
- RegisterDevice, DeregisterDevice, Logout

### E2BConfigService
- GetByClusterID, GetAvailable, ListAll

### EnterprisePreferenceService
- GetPreference, SetPreference, GetUserBanner, SetUserBanner
- GetDataControl, SetDataControlEnabled
- UpdateDataControlLevel, SetDataControlDefaultLevel

### FileService / AdminFileService
- SignUrl, BatchSignUrl, SandboxSignUrl, SandboxSignPrivateUrl

### CommunityInteractionService
- Like (community usecase likes)

### LiveEventService / LiveEventAdminService / LiveEventPublicService
- CheckLiveEvent, CreateEvent, UpdateEvent, ListEvents, DeleteEvent
- GetEventOverview, ListEventUsers, ListEventSessions, GetLiveEvent

### ActivityService / ActivityAdminService
- GetOrganizationInfoByUID, ListActivityOrganization
- CreateActivityOrganization, UpdateActivityOrganization

## Key Enums

### SessionStatus (13 values)
UNSPECIFIED, CREATED, ARCHIVED, DELETED, WAITING, RUNNING, STOPPED, ERROR,
IN_QUEUE, COLLABORATION_PERMISSION_CHANGED, NEW_COLLABORATOR,
REMOVE_COLLABORATOR, FROZEN

### AgentTaskMode
UNSPECIFIED, STANDARD, HIGH_EFFORT, LITE, DISCUSS

### Plan_Key (subscription tiers)
UNKNOWN, PRO_MONTHLY, CASUAL_MONTHLY, PRO_YEARLY, CASUAL_YEARLY,
LITE_MONTHLY, LITE_YEARLY, CREDITS_2000, CREDITS_10000, CREDITS_19900,
TEAM_MONTHLY, TEAM_YEARLY, TEAM_ADDON, TEAM_DEDUCTION

### SpaceStatus
INVISIBLE, VISIBLE, BAN

### CollaboratorPermission
UNSPECIFIED, READ_ONLY, READ_WRITE

### CreditType
UNSPECIFIED, FREE, PERIODIC, ADDON, EVENT, REFRESH

## Space Editor (Embedded Component)
The `spaceEditor-DPV-_I11.js` (22K lines) is injected into every deployed Space:
- Uses Lit HTML for templates (not React)
- Coloris color picker
- DOM patch system: selector + style mutations saved to server
- Undo/redo, version history, restore original
- Amplitude tracking + ThumbmarkJS fingerprinting
- Custom elements: manus-content-root, footer-watermark, lit-popup, lit-dialog

## Environment Variables (client-side)
```js
window.__manus_space_editor_info = {
  spaceId, patchList, hideBadge, sessionId, isWebDev, usageStatus
}
window.__manus__global_env = {
  apiHost,   // "https://api.manus.im"
  host,      // "https://manus.im"
  amplitudeKey
}
```

## Webapp Asset Inventory
- 44 JS chunks, 10 CSS files
- Largest: 1.9MB (Konva + Framer Motion + Shiki syntax highlighting)
- Protobuf chunk: 800KB (all service definitions)
- FPM loader: 178KB (Fingerprint Pro)
- PDF worker: 1.3MB
- Space Editor: ~22K lines standalone

## Notable Features Discovered
1. **Scheduled Tasks** — CreateScheduledTask, cron-like recurring sessions
2. **Figma Integration** — CreateFigmaParseTask, LoopFigmaParseTask
3. **Canvas/Design** — Upscale (2K/4K/8K), RemoveBackground, OCR
4. **Email Reception** — PageGetReceivedEmail, CheckHaveNoneReadEmail
5. **API Proxy** — User-configured external API calls through Manus
6. **Knowledge System** — User + builtin knowledge, events + approval flow
7. **E2B Integration** — E2BConfigService for sandbox infrastructure
8. **Enterprise** — Data control policies, team asset audit logs
9. **Live Events** — In-person event management with QR codes
10. **Document Suggestions** — GenerateDocumentSuggestion RPC
