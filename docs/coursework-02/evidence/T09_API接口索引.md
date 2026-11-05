# T09 后端 API 接口索引（Java / Python）

> 任务：Issue #26 · 负责人 S2（kwndl108）· 交付位置 `docs/coursework-02/evidence/T09_API接口索引.md`
> 代码基线：`fzu-404-team/kaoyan-agent-platform` main @ `db1c040 (main, 2026-11-05)`
> 生成方式：静态扫描源码注解（脚本口径见文末），**未展开 DTO 字段、不分析深层业务**。

## 0. 一页速览

| 项 | 数值 |
|---|---|
| Java Controller | **16 个**（全部覆盖） |
| Java 端点 | **94 个** |
| Python 端点（FastAPI） | **7 个** |
| 合计 | **101 个** |
| 后端服务 | `kaoyan-B` Spring Boot，默认端口 `8080`，统一返回 `Result<T>` |
| Agent 服务 | `kaoyan-agent` FastAPI，默认端口 `8001`，路径前缀 `/internal/rag` |
| 认证 | Java：`Authorization: Bearer <JWT>`（`JwtAuthenticationFilter`）；Python：内部令牌 `Depends(authenticate)` |

**列含义**：`方法 + 路径` 即对外契约；`Controller 方法` 是 Java 方法名；`首个 Service` 是方法体内第一个被调用的注入依赖，**不是完整调用链**；`源码位置` 为 `文件:行`，可直接跳转。

## 1. Java 接口（按 Controller 分组）

| Controller | 职责 | 端点数 | 类声明位置 |
|---|---|---|---|
| `AuthController` | 注册 / 登录 / 刷新令牌 / 登出 | 4 | `AuthController.java:25` |
| `UserController` | 个人资料、密码、账号设置 | 4 | `UserController.java:27` |
| `QuestionController` | 题库浏览、检索、详情、收藏、题目版本 | 11 | `QuestionController.java:34` |
| `PracticeController` | 刷题批次：开始、作答、交卷、结果、回顾 | 9 | `PracticeController.java:30` |
| `LearningController` | 学习诊断与学情：批次状态、进度、提示、画像、推荐设置、题目版本管理 | 15 | `LearningController.java:14` |
| `StatController` | 统计：学习数据、图表 | 4 | `StatController.java:23` |
| `RecommendController` | 院校推荐 | 3 | `RecommendController.java:22` |
| `SchoolController` | 院校库查询与详情 | 4 | `SchoolController.java:24` |
| `DocumentController` | 公开资料文档 | 6 | `DocumentController.java:26` |
| `PersonalDocumentController` | 个人资料 / 笔记文档 | 6 | `PersonalDocumentController.java:13` |
| `FileController` | 文件上传与下载 | 2 | `FileController.java:24` |
| `ExportController` | 数据导出 | 3 | `ExportController.java:15` |
| `MarkController` | 标注 / 书签 | 6 | `MarkController.java:21` |
| `TaskController` | 异步任务状态查询 | 3 | `TaskController.java:24` |
| `ConversationController` | 助手会话与聊天流（含流式） | 12 | `ConversationController.java:15` |
| `AssistantPrivacyController` | 助手隐私设置 | 2 | `AssistantPrivacyController.java:13` |

### 1.1 `AuthController` · 注册 / 登录 / 刷新令牌 / 登出（4 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/AuthController.java`　类声明行号：25

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | POST | `/api/auth/register` | `register` | @Valid @RequestBody RegisterRequest req | `Result<?>` | `UserService` | `AuthController.java:33` |
| 2 | POST | `/api/auth/login` | `login` | @Valid @RequestBody LoginRequest req | `Result<Map<String, String>>` | `UserService` | `AuthController.java:42` |
| 3 | POST | `/api/auth/refresh` | `refresh` | @Valid @RequestBody RefreshRequest req | `Result<Map<String, String>>` | `UserService` | `AuthController.java:52` |
| 4 | POST | `/api/auth/logout` | `logout` | @RequestHeader("Authorization") String authorization | `Result<Void>` | `UserService` | `AuthController.java:62` |

### 1.2 `UserController` · 个人资料、密码、账号设置（4 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/UserController.java`　类声明行号：27

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | PUT | `/api/users/avatar` | `updateAvatar` | @Valid @RequestBody AvatarRequest req | `Result<Void>` | `UserService` | `UserController.java:44` |
| 2 | PUT | `/api/users/profile` | `updateProfile` | @Valid @RequestBody ProfileRequest req | `Result<Void>` | `UserService` | `UserController.java:56` |
| 3 | GET | `/api/users/avatar/content` | `avatarContent` | — | `ResponseEntity<byte[]>` | `UserService` | `UserController.java:67` |
| 4 | GET | `/api/users/me` | `me` | — | `Result<User>` | `UserService` | `UserController.java:84` |

### 1.3 `QuestionController` · 题库浏览、检索、详情、收藏、题目版本（11 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/QuestionController.java`　类声明行号：34

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/questions/practice` | `practice` | QuestionPracticeQuery query | `Result<List<StudentQuestionVO>>` | `QuestionService` | `QuestionController.java:42` |
| 2 | GET | `/api/questions/{id}` | `detail` | @PathVariable Long id | `Result<StudentQuestionVO>` | `QuestionService` | `QuestionController.java:53` |
| 3 | GET | `/api/questions/admin/pending` | `pending` | PageQuery query | `Result<PageResult<Question>>` | `QuestionService` | `QuestionController.java:64` |
| 4 | POST | `/api/questions/admin` | `create` | @Valid @RequestBody QuestionEntryRequest request | `Result<Question>` | `QuestionService` | `QuestionController.java:73` |
| 5 | POST | `/api/questions/admin/import/preview` | `previewImport` | @Valid @RequestBody QuestionImportRequest request | `Result<QuestionImportVO>` | `QuestionService` | `QuestionController.java:79` |
| 6 | POST | `/api/questions/admin/import` | `importQuestions` | @Valid @RequestBody QuestionImportRequest request | `Result<QuestionImportVO>` | `QuestionService` | `QuestionController.java:86` |
| 7 | GET | `/api/questions/admin/{id}` | `adminDetail` | @PathVariable Long id | `Result<Question>` | `QuestionService` | `QuestionController.java:93` |
| 8 | PUT | `/api/questions/admin/{id}` | `update` | @PathVariable Long id, @Valid @RequestBody Question… | `Result<Question>` | `QuestionService` | `QuestionController.java:102` |
| 9 | PUT | `/api/questions/admin/{id}/active` | `active` | @PathVariable Long id, @Valid @RequestBody Question… | `Result<Question>` | `QuestionService` | `QuestionController.java:108` |
| 10 | DELETE | `/api/questions/admin/{id}` | `delete` | @PathVariable Long id | `Result<Void>` | `QuestionService` | `QuestionController.java:117` |
| 11 | POST | `/api/questions/admin/{id}/review` | `review` | @PathVariable Long id, @Valid @RequestBody Question… | `Result<Void>` | `QuestionService` | `QuestionController.java:127` |

### 1.4 `PracticeController` · 刷题批次：开始、作答、交卷、结果、回顾（9 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/PracticeController.java`　类声明行号：30

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | POST | `/api/practice/sessions` | `start` | @Valid @RequestBody StartSessionRequest req | `Result<Map<String, String>>` | `PracticeService` | `PracticeController.java:40` |
| 2 | POST | `/api/practice/sessions/{sessionId}/answer` | `answer` | @PathVariable String sessionId, @Valid @RequestBody… | `Result<?>` | `PracticeService` | `PracticeController.java:51` |
| 3 | GET | `/api/practice/sessions/{sessionId}/summary` | `summary` | @PathVariable String sessionId | `Result<Map<String, Object>>` | `PracticeService` | `PracticeController.java:65` |
| 4 | POST | `/api/practice/sessions/{sessionId}/ai-summary` | `aiSummary` | @PathVariable String sessionId | `Result<TaskView>` | `TaskService` | `PracticeController.java:71` |
| 5 | GET | `/api/practice/sessions` | `sessions` | — | `Result<List<String>>` | `PracticeService` | `PracticeController.java:83` |
| 6 | GET | `/api/practice/sessions/page` | `sessionsPage` | @RequestParam(defaultValue = "1") int pageNum, @Req… | `Result<PageResult<SessionSummaryV…` | `PracticeService` | `PracticeController.java:89` |
| 7 | GET | `/api/practice/sessions/{sessionId}` | `detail` | @PathVariable String sessionId | `Result<List<PracticeRecordVO>>` | `PracticeService` | `PracticeController.java:100` |
| 8 | GET | `/api/practice/sessions/{sessionId}/review` | `review` | @PathVariable String sessionId, @RequestParam(defau… | `Result<PageResult<ReviewRecordVO>>` | `PracticeService` | `PracticeController.java:106` |
| 9 | DELETE | `/api/practice/sessions/{sessionId}` | `abandon` | @PathVariable String sessionId | `Result<Void>` | `PracticeService` | `PracticeController.java:118` |

### 1.5 `LearningController` · 学习诊断与学情：批次状态、进度、提示、画像、推荐设置、题目版本管理（15 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/learning/LearningController.java`　类声明行号：14

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/learning/status` | `status` | — | `Result<Map<String,Object>>` | `ManagedPracticeService` | `LearningController.java:21` |
| 2 | POST | `/api/diagnostics/sessions` | `diagnose` | — | `Result<Map<String,Object>>` | `ManagedPracticeService` | `LearningController.java:22` |
| 3 | GET | `/api/practice/sessions/{id}/state` | `state` | @PathVariable String id | `Result<State>` | `ManagedPracticeService` | `LearningController.java:23` |
| 4 | PUT | `/api/practice/sessions/{id}/progress` | `progress` | @PathVariable String id,@Valid @RequestBody Progres… | `Result<State>` | `ManagedPracticeService` | `LearningController.java:24` |
| 5 | POST | `/api/practice/sessions/{id}/finish` | `finish` | @PathVariable String id | `Result<Map<String,Object>>` | `ManagedPracticeService` | `LearningController.java:25` |
| 6 | GET | `/api/practice/sessions/{id}/result` | `result` | @PathVariable String id | `Result<Map<String,Object>>` | `ManagedPracticeService` | `LearningController.java:26` |
| 7 | POST | `/api/practice/sessions/{id}/items/{item}/hints` | `hint` | @PathVariable String id,@PathVariable long item,@Va… | `Result<Map<String,Object>>` | `ManagedPracticeService` | `LearningController.java:27` |
| 8 | GET | `/api/learning/profile` | `profile` | — | `Result<Profile>` | `LearningProfiles` | `LearningController.java:28` |
| 9 | GET | `/api/learning/profile/history` | `history` | @RequestParam(defaultValue="1") int pageNum,@Reques… | `Result<Map<String,Object>>` | `LearningProfiles` | `LearningController.java:29` |
| 10 | GET | `/api/learning/recommendation-settings` | `settings` | — | `Result<Map<String,Object>>` | `LearningRecommendations` | `LearningController.java:30` |
| 11 | PUT | `/api/learning/recommendation-settings` | `settings` | @Valid @RequestBody Settings req | `Result<Map<String,Object>>` | `LearningRecommendations` | `LearningController.java:31` |
| 12 | POST | `/api/learning/admin/blueprints` | `publish` | @Valid @RequestBody Blueprint req | `Result<Map<String,Object>>` | `LearningProfiles` | `LearningController.java:32` |
| 13 | POST | `/api/learning/admin/historical-metrics` | `metric` | @Valid @RequestBody Metric req | `Result<Map<String,Object>>` | `LearningRecommendations` | `LearningController.java:35` |
| 14 | POST | `/api/questions/admin/{id}/versions` | `revision` | @PathVariable long id,@Valid @RequestBody Revision … | `Result<Map<String,Object>>` | `ManagedPracticeService` | `LearningController.java:38` |
| 15 | POST | `/api/questions/admin/{id}/versions/{version}/withdraw` | `withdraw` | @PathVariable long id,@PathVariable int version,@Va… | `Result<Void>` | `ManagedPracticeService` | `LearningController.java:41` |

### 1.6 `StatController` · 统计：学习数据、图表（4 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/StatController.java`　类声明行号：23

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/stats/today` | `today` | — | `Result<StudyStat>` | `StudyStatService` | `StatController.java:31` |
| 2 | GET | `/api/stats/range` | `range` | StatRangeQuery query | `Result<List<StudyStat>>` | `StudyStatService` | `StatController.java:40` |
| 3 | GET | `/api/stats/overview` | `overview` | — | `Result<Map<String, Object>>` | `StudyStatService` | `StatController.java:50` |
| 4 | GET | `/api/stats/learning` | `learning` | @RequestParam(required = false) java.time.LocalDate… | `Result<Map<String, Object>>` | `StudyStatService` | `StatController.java:54` |

### 1.7 `RecommendController` · 院校推荐（3 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/RecommendController.java`　类声明行号：22

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | POST | `/api/recommends/generate` | `generate` | @RequestBody(required = false) Map<String, Object> … | `Result<TaskView>` | `RecommendService` | `RecommendController.java:30` |
| 2 | GET | `/api/recommends` | `list` | — | `Result<List<TaskView>>` | `RecommendService` | `RecommendController.java:39` |
| 3 | DELETE | `/api/recommends/{id}` | `delete` | @PathVariable String id | `Result<Void>` | `RecommendService` | `RecommendController.java:48` |

### 1.8 `SchoolController` · 院校库查询与详情（4 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/SchoolController.java`　类声明行号：24

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/schools/options` | `options` | — | `Result<SchoolOptionsVO>` | `SchoolService` | `SchoolController.java:29` |
| 2 | GET | `/api/schools` | `search` | @Parameter(description = "省份", example = "北京") @Req… | `Result<List<School>>` | `SchoolService` | `SchoolController.java:38` |
| 3 | POST | `/api/schools/search` | `searchByBody` | @RequestBody SchoolQuery query | `Result<List<School>>` | `SchoolService` | `SchoolController.java:53` |
| 4 | GET | `/api/schools/{schoolId}` | `detail` | @PathVariable Long schoolId | `Result<Map<String, Object>>` | `SchoolService` | `SchoolController.java:62` |

### 1.9 `DocumentController` · 公开资料文档（6 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/DocumentController.java`　类声明行号：26

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/documents` | `listPublished` | DocumentQuery query | `Result<List<Document>>` | `DocumentService` | `DocumentController.java:34` |
| 2 | GET | `/api/documents/admin/list` | `adminList` | DocumentAdminQuery query | `Result<PageResult<Document>>` | `DocumentService` | `DocumentController.java:43` |
| 3 | POST | `/api/documents/admin` | `create` | @RequestBody Document doc | `Result<Document>` | `DocumentService` | `DocumentController.java:53` |
| 4 | PUT | `/api/documents/admin/{id}` | `update` | @PathVariable Long id, @RequestBody Document doc | `Result<Void>` | `DocumentService` | `DocumentController.java:62` |
| 5 | DELETE | `/api/documents/admin/{id}` | `delete` | @PathVariable Long id | `Result<Void>` | `DocumentService` | `DocumentController.java:72` |
| 6 | POST | `/api/documents/admin/{id}/review` | `review` | @PathVariable Long id, @Valid @RequestBody ReviewRe… | `Result<Void>` | `DocumentService` | `DocumentController.java:82` |

### 1.10 `PersonalDocumentController` · 个人资料 / 笔记文档（6 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/PersonalDocumentController.java`　类声明行号：13

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/personal-documents` | `list` | @RequestParam(defaultValue="1") int pageNum,@Reques… | `Result<Map<String,Object>>` | `PersonalDocumentService` | `PersonalDocumentController.java:15` |
| 2 | GET | `/api/personal-documents/{id}` | `get` | @PathVariable String id | `Result<Map<String,Object>>` | `PersonalDocumentService` | `PersonalDocumentController.java:19` |
| 3 | GET | `/api/personal-documents/{id}/versions` | `versions` | @PathVariable String id,@RequestParam(defaultValue=… | `Result<Map<String,Object>>` | `PersonalDocumentService` | `PersonalDocumentController.java:21` |
| 4 | POST | `/api/personal-documents` | `create` | @RequestBody PersonalDocumentService.Save input | `Result<Map<String,Object>>` | `PersonalDocumentService` | `PersonalDocumentController.java:25` |
| 5 | GET | `/api/personal-documents/{id}/versions/{version}` | `version` | @PathVariable String id,@PathVariable int version | `Result<Map<String,Object>>` | `PersonalDocumentService` | `PersonalDocumentController.java:29` |
| 6 | PUT | `/api/personal-documents/{id}` | `update` | @PathVariable String id,@RequestBody PersonalDocume… | `Result<Map<String,Object>>` | `PersonalDocumentService` | `PersonalDocumentController.java:33` |

### 1.11 `FileController` · 文件上传与下载（2 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/FileController.java`　类声明行号：24

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | POST | `/api/files/upload` | `upload` | @RequestParam("file") MultipartFile file, @RequestP… | `Result<Map<String, String>>` | `OssUtil` | `FileController.java:37` |
| 2 | DELETE | `/api/files` | `delete` | @RequestParam("objectKey") String objectKey | `Result<Void>` | `OssUtil` | `FileController.java:51` |

### 1.12 `ExportController` · 数据导出（3 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/ExportController.java`　类声明行号：15

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | POST | `/api/exports/preview` | `preview` | @RequestBody JsonNode input | `ResponseEntity<Result<Preview>>` | `ExportService` | `ExportController.java:18` |
| 2 | GET | `/api/exports/{id}` | `get` | @PathVariable String id | `ResponseEntity<Result<Preview>>` | `ExportService` | `ExportController.java:23` |
| 3 | GET | `/api/exports/{id}/file` | `file` | @PathVariable String id, @RequestParam String format | `ResponseEntity<byte[]>` | `ExportService` | `ExportController.java:28` |

### 1.13 `MarkController` · 标注 / 书签（6 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/MarkController.java`　类声明行号：21

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | POST | `/api/marks/wrong/{questionId}` | `markWrong` | @PathVariable Long questionId | `Result<Void>` | `UserQuestionMarkService` | `MarkController.java:29` |
| 2 | DELETE | `/api/marks/wrong/{questionId}` | `removeWrong` | @PathVariable Long questionId | `Result<Void>` | `UserQuestionMarkService` | `MarkController.java:39` |
| 3 | POST | `/api/marks/favorite/{questionId}` | `favorite` | @PathVariable Long questionId | `Result<Void>` | `UserQuestionMarkService` | `MarkController.java:49` |
| 4 | DELETE | `/api/marks/favorite/{questionId}` | `unfavorite` | @PathVariable Long questionId | `Result<Void>` | `UserQuestionMarkService` | `MarkController.java:59` |
| 5 | GET | `/api/marks/wrong` | `wrongList` | @RequestParam(defaultValue = "1") int pageNum, @Req… | `Result<PageResult<MarkQuestionVO>>` | `UserQuestionMarkService` | `MarkController.java:66` |
| 6 | GET | `/api/marks/favorite` | `favoriteList` | @RequestParam(defaultValue = "1") int pageNum, @Req… | `Result<PageResult<MarkQuestionVO>>` | `UserQuestionMarkService` | `MarkController.java:74` |

### 1.14 `TaskController` · 异步任务状态查询（3 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/TaskController.java`　类声明行号：24

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | POST | `/api/tasks` | `submit` | @Valid @RequestBody TaskSubmitRequest req | `Result<TaskView>` | `TaskService` | `TaskController.java:32` |
| 2 | GET | `/api/tasks` | `history` | PageQuery query | `Result<PageResult<TaskView>>` | `TaskService` | `TaskController.java:41` |
| 3 | GET | `/api/tasks/{taskId}` | `detail` | @PathVariable String taskId | `Result<TaskView>` | `TaskService` | `TaskController.java:53` |

### 1.15 `ConversationController` · 助手会话与聊天流（含流式）（12 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/ConversationController.java`　类声明行号：15

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | POST | `/api/conversations` | `create` | — | `Result<Map<String,Object>>` | `ConversationService` | `ConversationController.java:17` |
| 2 | DELETE | `/api/conversations` | `clearAll` | — | `Result<Void>` | `ConversationService` | `ConversationController.java:18` |
| 3 | DELETE | `/api/conversations/{id}` | `clear` | @PathVariable String id | `Result<Void>` | `ConversationService` | `ConversationController.java:19` |
| 4 | POST | `/api/conversations/{id}/actions/{actionId}/confirm` | `confirm` | @PathVariable String id,@PathVariable String action… | `Result<Map<String,Object>>` | `ConversationService` | `ConversationController.java:20` |
| 5 | POST | `/api/conversations/{id}/actions/{actionId}/dismiss` | `dismiss` | @PathVariable String id,@PathVariable String action… | `Result<Map<String,Object>>` | `ConversationService` | `ConversationController.java:23` |
| 6 | GET | `/api/conversations` | `list` | @RequestParam(defaultValue="1") int pageNum,@Reques… | `Result<Map<String,Object>>` | `ConversationService` | `ConversationController.java:26` |
| 7 | GET | `/api/conversations/{id}/messages` | `messages` | @PathVariable String id,@RequestParam(defaultValue=… | `Result<Map<String,Object>>` | `ConversationService` | `ConversationController.java:29` |
| 8 | POST | `/api/conversations/{id}/messages` | `send` | @PathVariable String id,@RequestBody ConversationSe… | `Result<Map<String,Object>>` | `ConversationService` | `ConversationController.java:32` |
| 9 | POST | `/api/conversations/{id}/messages/{messageId}/retry` | `retry` | @PathVariable String id,@PathVariable String messag… | `Result<Map<String,Object>>` | `ConversationService` | `ConversationController.java:35` |
| 10 | GET | `/api/conversations/{id}/generations/{taskId}/stream` | `stream` | @PathVariable String id,@PathVariable String taskId… | `SseEmitter` | `ConversationService` | `ConversationController.java:38` |
| 11 | POST | `/api/conversations/{id}/generations/{taskId}/cancel` | `cancel` | @PathVariable String id,@PathVariable String taskId | `Result<Map<String,Object>>` | `ConversationService` | `ConversationController.java:43` |
| 12 | POST | `/api/conversations/{id}/generations/{taskId}/apply-document` | `apply` | @PathVariable String id,@PathVariable String taskId… | `Result<Map<String,Object>>` | `ConversationService` | `ConversationController.java:46` |

### 1.16 `AssistantPrivacyController` · 助手隐私设置（2 个）

源码：`kaoyan-B/src/main/java/com/kaoyan/controller/AssistantPrivacyController.java`　类声明行号：13

| # | 方法 | 路径 | Controller 方法 | 请求参数 | 返回类型 | 首个 Service | 源码位置 |
|---|---|---|---|---|---|---|---|
| 1 | GET | `/api/privacy/settings` | `get` | — | `Result<Map<String,Object>>` | `AssistantPrivacyService` | `AssistantPrivacyController.java:15` |
| 2 | PUT | `/api/privacy/settings` | `save` | @RequestBody AssistantPrivacyService.Save input | `Result<Map<String,Object>>` | `AssistantPrivacyService` | `AssistantPrivacyController.java:16` |

## 2. Python 接口（FastAPI）

源码：`kaoyan-agent/main.py`（`create_app` 工厂内以 `@app` 装饰器注册）

| # | 方法 | 路径 | 处理函数 | 请求参数 | 首个业务对象 | 源码位置 |
|---|---|---|---|---|---|---|
| 1 | GET | `/health` | `health` | — | `corpus` | `main.py:122` |
| 2 | POST | `/internal/rag/questions/index` | `question_index_submit` | req: IndexRequest | `question_index` | `main.py:140` |
| 3 | GET | `/internal/rag/questions/index/{release_id}` | `question_index_status` | release_id: str | `question_index` | `main.py:144` |
| 4 | POST | `/internal/rag/questions/search` | `question_search` | req: SearchRequest | `question_index` | `main.py:153` |
| 5 | POST | `/internal/rag/conversation/plan` | `conversation_plan` | req: ConversationRequest | `conversation` | `main.py:163` |
| 6 | POST | `/internal/rag/chat` | `chat` | req: ChatRequest | `engine` | `main.py:186` |
| 7 | POST | `/internal/rag/conversation/stream` | `conversation_stream` | req: ConversationRequest | `conversation` | `main.py:217` |

**Python 端点用途**（供 T03/T05 写时序时引用）：

| 路径 | 用途 |
|---|---|
| `POST /internal/rag/questions/index` | 触发题库向量索引构建（异步），返回 releaseId |
| `GET /internal/rag/questions/index/{release_id}` | 查询索引构建进度 |
| `POST /internal/rag/questions/search` | 题库语义检索 |
| `POST /internal/rag/conversation/plan` | 会话规划（是否检索、是否调用工具） |
| `POST /internal/rag/chat` | 单轮 Agent 任务执行（非流式） |
| `POST /internal/rag/conversation/stream` | **聊天流**：SSE 逐步推送 stage / 增量回答 |
| `GET /health` | 健康检查（不带认证） |

## 3. 重点链路索引（对应验收：learning / 聊天流 / 隐私 / 文件 / 导出）

### 3.1 learning（学情与诊断）

| 端点 | 作用 | 源码 |
|---|---|---|
| `GET /api/learning/status` | 功能开关状态 | `LearningController.java:21` |
| `POST /api/diagnostics/sessions` | 诊断批次创建 | `LearningController.java:22` |
| `GET /api/practice/sessions/{id}/state` | 批次状态（断点续做） | `LearningController.java:23` |
| `PUT /api/practice/sessions/{id}/progress` | 进度上报 | `LearningController.java:24` |
| `POST /api/practice/sessions/{id}/finish` | 交卷 | `LearningController.java:25` |
| `GET /api/practice/sessions/{id}/result` | 结果总览 | `LearningController.java:26` |
| `POST /api/practice/sessions/{id}/items/{item}/hints` | 分级提示 | `LearningController.java:27` |
| `GET /api/learning/profile` | 学情画像 | `LearningController.java:28` |
| `GET /api/learning/profile/history` | 学情历史 | `LearningController.java:29` |
| `GET /api/learning/recommendation-settings` | 推荐偏好 | `LearningController.java:30` |
| `PUT /api/learning/recommendation-settings` | 推荐偏好 | `LearningController.java:31` |
| `POST /api/learning/admin/blueprints` | 学情蓝图（管理员） | `LearningController.java:32` |
| `POST /api/learning/admin/historical-metrics` | 历史指标（管理员） | `LearningController.java:35` |
| `POST /api/questions/admin/{id}/versions` | 题目版本（管理员） | `LearningController.java:38` |
| `POST /api/questions/admin/{id}/versions/{version}/withdraw` | 题目版本（管理员） | `LearningController.java:41` |

> 注意：该类全部端点由 `ObjectProvider<...>` 条件装配，**迁移未启用时返回 503**（`诊断与学情功能尚未启用`），T05 画时序时要体现这个降级分支。

### 3.2 聊天流（Agent 会话）

| 层级 | 端点 | 说明 | 源码 |
|---|---|---|---|
| Java | `GET /api/conversations/{id}/generations/{taskId}/stream` | 前端入口，转发到 Agent | `ConversationController.java:38` |
| Python | `POST /internal/rag/chat` | 非流式：一次性返回 `ChatResponse` | `main.py:186` |
| Python | `POST /internal/rag/conversation/stream` | **流式（SSE）**：逐条推送 stage / 增量文本 | `main.py:217` |

**Java 侧怎么打到这些 Python 端点**（T05 画时序可直接抄这张表）：

| Python 端点 | Java 调用方式 | 调用位置 |
|---|---|---|
| `POST /internal/rag/conversation/plan` | 原生 `java.net.http.HttpClient` | `ConversationService.java:326` |
| `POST /internal/rag/conversation/stream` | 原生 `java.net.http.HttpClient`（读 SSE 再转发前端） | `ConversationService.java:373` |
| `POST /internal/rag/chat` | OpenFeign `AgentFeignClient` | `AgentFeignClient.java:18` |
| `POST /internal/rag/questions/index` | 原生 `HttpClient`（建索引快照） | `QuestionSearchService.java:43` |
| `POST /internal/rag/questions/search` | 原生 `HttpClient`（向量检索） | `QuestionSearchService.java:56` |

注意：只有非流式 `/chat` 走 Feign，其余四条都是手写 `HttpClient`（要自控超时和流式读取）。画时序时不要把五条都画成 Feign。

### 3.3 隐私

- `GET /api/privacy/settings` → `AssistantPrivacyService` · `AssistantPrivacyController.java:15`
- `PUT /api/privacy/settings` → `AssistantPrivacyService` · `AssistantPrivacyController.java:16`

### 3.4 文件

- `GET /api/documents` → `DocumentService` · `DocumentController.java:34`
- `GET /api/documents/admin/list` → `DocumentService` · `DocumentController.java:43`
- `POST /api/documents/admin` → `DocumentService` · `DocumentController.java:53`
- `PUT /api/documents/admin/{id}` → `DocumentService` · `DocumentController.java:62`
- `DELETE /api/documents/admin/{id}` → `DocumentService` · `DocumentController.java:72`
- `POST /api/documents/admin/{id}/review` → `DocumentService` · `DocumentController.java:82`
- `POST /api/files/upload` → `OssUtil` · `FileController.java:37`
- `DELETE /api/files` → `OssUtil` · `FileController.java:51`
- `GET /api/personal-documents` → `PersonalDocumentService` · `PersonalDocumentController.java:15`
- `GET /api/personal-documents/{id}` → `PersonalDocumentService` · `PersonalDocumentController.java:19`
- `GET /api/personal-documents/{id}/versions` → `PersonalDocumentService` · `PersonalDocumentController.java:21`
- `POST /api/personal-documents` → `PersonalDocumentService` · `PersonalDocumentController.java:25`
- `GET /api/personal-documents/{id}/versions/{version}` → `PersonalDocumentService` · `PersonalDocumentController.java:29`
- `PUT /api/personal-documents/{id}` → `PersonalDocumentService` · `PersonalDocumentController.java:33`

### 3.5 导出

- `POST /api/exports/preview` → `ExportService` · `ExportController.java:18`
- `GET /api/exports/{id}` → `ExportService` · `ExportController.java:23`
- `GET /api/exports/{id}/file` → `ExportService` · `ExportController.java:28`

## 4. 给下游的使用说明

**T03（接口章节）**：直接引用第 1、2 节的表；架构叙述时用「Java 负责业务与持久化，Agent 只做检索与生成」这条边界（见 3.2）。

**T05（时序定位）**：时序图里的每个箭头都能在本文件找到落点，例如

- 开始批次 → `POST /api/practice/sessions`（`PracticeController.java:40`）
- 作答 → `POST /api/practice/sessions/{sessionId}/answer`（`PracticeController.java:51`）
- 聊天流 → `GET /api/conversations/{id}/generations/{taskId}/stream`（Java，`ConversationController.java:38`）→ `POST /internal/rag/conversation/stream`（Python SSE）

**核对提示**：若发现本表缺项，请在下游 Issue 留言，我按 `文件:行` 补齐。

## 5. 覆盖自检

| 检查项 | 结果 |
|---|---|
| 要求覆盖 16 个 Controller | ✅ 16/16 |
| 要求覆盖 Python 端点 | ✅ 7 个（`main.py` 全部 `@app` 路由） |
| learning 链路 | ✅ 第 3.1 节，15 个端点 |
| 聊天流 | ✅ 第 3.2 节，Java 入口 + Python 执行端 |
| 隐私 | ✅ 第 3.3 节，2 个端点 |
| 文件 | ✅ 第 3.4 节，15 个端点（File / PersonalDocument / Document） |
| 导出 | ✅ 第 3.5 节，3 个端点 |
| 每条都有源码行号 | ✅ 全部 |

## 6. 口径与已知边界

1. **扫描口径**：Java 取 `@RestController` 类上 `@RequestMapping` 前缀 + 方法级 `@Get/Post/Put/Delete/PatchMapping`；类级别 `@RequestMapping` 不计为端点。
2. **路径拼接**：类前缀 + 方法路径，已归一化（去重复 `/`）；`{id}` 这类占位符原样保留。
3. **首个 Service**：按方法体里第一个出现的注入字段判定，遇到 `ObjectProvider<T>` 时取 `T`；它只表示「第一跳」，不代表完整依赖图。
4. **未覆盖**：DTO 字段明细、参数校验注解语义、Service 内部实现、拦截器/过滤器链——按任务要求不展开。
5. **复现方式**：`tools/scan_api.py`（本地脚本，扫描 tar 快照后生成 `api-index.json` 再渲染本文件）；如需重跑，把仓库解压后改 `ROOT` 即可。
