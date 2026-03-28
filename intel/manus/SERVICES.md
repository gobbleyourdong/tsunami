# Manus Protobuf Services Reference
> Extracted from files.manuscdn.com/webapp chunks, 2026-03-28

## Session Management (session.v1)

### SessionService
Core agent session lifecycle.
```
GetSession, ListSessions, ListSessionsV2, SearchSessions
UpdateReadPosition, FavoriteSession, UnfavoriteSession
UpdateSession, DeleteSession, ShareSession, UnshareSession
SessionFeedback, GetTaskQueueInfo, Search
```

### Scheduling (cron-like recurring tasks)
```
CreateScheduledTask, ListScheduledTasks, UpdateScheduledTask
DeleteScheduledTask, GetCompletedScheduledSessions
GetScheduledTaskStatus, ListScheduledTasksWithSessions
ListSessionsByScheduledTask
```

### Slides & Templates
```
ListSlideTemplates, GetSlideTemplateStatus
DeleteSlideTemplate, RenameSlideTemplate
ListSessionTemplates, GenerateDocumentSuggestion
```

### Files & Versioning
```
ListSessionFileVersions
CreateFigmaParseTask, LoopFigmaParseTask
WebPageScreenShotFullPage
```

### Email Integration
```
PageGetReceivedEmail, GetReceivedEmailDetail
CheckHaveNoneReadEmail
```

### Collaboration (session.v1)
```
ListCollaborators, InviteCollaborator, RemoveCollaborator
UpdateCollaboratorPermission, AcceptInvite, RejectInvite
ExitCollaboration, MemberRequest, ProcessRequest
JoinSessionCollaborationForTeam
```

### Community
```
ListRecommendUsecases
ShareSessionToCommunity, UnshareSessionFromCommunity
SubmitSessionResponseFeedback
```

## Canvas & Image (session.v1 / bizimage.v1)

### CanvasService
```
UpsertCanvas, UpsertCanvasS3, GetCanvas, DeleteCanvas
BatchUpsertCanvas, Upscale, GetUpscaleResult
RemoveBackground, GetRemoveBackgroundResult
```

### ImageService
```
OCR, GenerateImage, MarkGenerateImage
```

Upscale supports: 2K, 4K, 8K resolution enum.

## User & Auth (user.v1)

### UserService
```
UserInfo, CheckInvitationCode, UpdateUserProfile
CreateQuestionnaire, GetFreeQuota, GetAvailableCredits
GetPersonalInvitationCodes, SetUserInterests
GetConnectAPP, DisconnectAPP
GetGoogleDriveAuthUrl, GetOneDrivePersonalAuthUrl
SendPhoneVerificationCode, BindPhoneTrait
InExperimentGroup
```

### UserAuthService
```
Logout, DeleteUser, SendEmailVerifyCodeWithAuth
ResetPasswordWithAuth, GenerateTempAuthCode
UpdateADID, UpdateEmail, VerifyEmail
```

### Subscription
```
Query, Update, Preview, Checkout, Cancel, Resume, BillingPage
TeamSubscriptionCheckout, TeamSubscriptionUpdate
TeamSubscriptionPreview, LoopTeamUpgradeStatus
```

## Team Management (team.v1)

### TeamManagementService
```
CreateTeam, UpdateTeamInfo, BatchInviteUser
DismissTeam, TransferTeam, BatchRemoveMember
UpdateMemberRole, UpdateTeamStep, UpdateInviteRole
UpdateTeamDeductionSetting, UpdateTeamPurchaseSetting
BatchDeactivateTeamMembers, ActiveTeamMember
CreateApiCredential, ListApiCredentials, DeleteApiCredential
```

### TeamAssetService
```
SetTeamSessionAccess, SetTeamAssetControl
ListTeamAssetControl, ListTeamAssetControlAuditLog
ListTeamAssetShare, UpdateTeamAssetShare
ListTeamAssetAuditLog
```

## Space / Deployment (space.v1)

### SpaceService
```
SetSpaceStatus, GetSpaceStatus, PageGetUserSpaces
EditSpaceSubDomain, GetEditSpaceSiteCode
HasSpaceEditPermission, SaveSpaceSiteRawData
RestoreOriginalSite
```

### SpacePublicService
```
GetSpaceDetail, GetSpaceStatus, GetEditSpaceSiteToken
```

### SpaceAdminService
```
BlockSpace, UnblockSpace, SpaceBlockList
AuditSpaceSubDomain, PageGetAuditSpaceSubDomain
```

## Knowledge (knowledge.v1)

### KnowledgeService
```
ListKnowledge, CreateKnowledge, UpdateKnowledge, DeleteKnowledge
ListKnowledgeEvents, UpdateKnowledgeEventStatus
GetKnowledgeDetail, UpdateKnowledgeEnabled
GetBuiltinKnowledge, UpdateKnowledgeEvent
```

## API Proxy (apiproxy.v1)
User-configured external API passthrough.
```
CallApi (user-facing)
CreateApi, UpdateApi, DeleteApi, GetApi, ListApi (admin)
```

## Enterprise (enterprise.v1)
```
GetPreference, SetPreference
GetDataControl, SetDataControlEnabled
UpdateDataControlLevel, SetDataControlDefaultLevel
```

## Infrastructure

### FileService (file.v1)
```
SignUrl, BatchSignUrl, SandboxSignUrl, SandboxSignPrivateUrl
```

### E2BConfigService (config.v1)
Sandbox infrastructure.
```
GetByClusterID, GetAvailable, ListAll
```

### NotifierService (notifier.v1)
```
RegisterDevice, DeregisterDevice, Logout
GetNotificationList, GetNotificationListV2
```

## Key Enums

### SessionStatus
UNSPECIFIED, CREATED, ARCHIVED, DELETED, WAITING, RUNNING,
STOPPED, ERROR, IN_QUEUE, COLLABORATION_PERMISSION_CHANGED,
NEW_COLLABORATOR, REMOVE_COLLABORATOR, FROZEN

### AgentTaskMode
UNSPECIFIED, STANDARD, HIGH_EFFORT, LITE, DISCUSS

### Plan_Key
UNKNOWN, PRO_MONTHLY, CASUAL_MONTHLY, PRO_YEARLY, CASUAL_YEARLY,
LITE_MONTHLY, LITE_YEARLY, CREDITS_2000, CREDITS_10000, CREDITS_19900,
TEAM_MONTHLY, TEAM_YEARLY, TEAM_ADDON, TEAM_DEDUCTION

### SpaceStatus
INVISIBLE, VISIBLE, BAN

### CollaboratorPermission
UNSPECIFIED, READ_ONLY, READ_WRITE

### CreditType
UNSPECIFIED, FREE, PERIODIC, ADDON, EVENT, REFRESH
