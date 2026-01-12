# BizContent AI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![React 19.2](https://img.shields.io/badge/react-19.2-blue.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg)](https://fastapi.tiangolo.com/)

> **소상공인을 위한 AI 콘텐츠 크리에이터**

AI Agent 기반 마케팅 콘텐츠 자동 생성 플랫폼 — 블로그, SNS, 동영상을 한 번에 생성하고 7개 플랫폼에 통합 발행

---

## 🎬 서비스 시연

<!-- TODO: GitHub Issue에 동영상 업로드 후 아래 링크 교체 -->
<!-- 업로드 방법: Issues → New Issue → 동영상 드래그앤드롭 → 생성된 URL 복사 -->


<!-- 업로드 완료 후 위 코드블록을 제거하고 아래처럼 수정:

https://github.com/user-attachments/assets/fb1ea390-018a-432c-b721-3f20dda68017.mp4

-->

---

## 🎯 프로젝트 목적

**소상공인 및 1인 기업인들이 효율적으로 마케팅할 수 있도록 지원**

### 배경

- 1인 기업과 소상공인은 **제한된 시간과 리소스**로 인해 효과적인 마케팅 콘텐츠를 지속적으로 생산하기 어렵습니다.
- 다양한 플랫폼(Instagram, Facebook, YouTube, 블로그 등)에 맞는 콘텐츠를 각각 제작하고 관리하는 것은 많은 시간과 노력이 필요합니다.

### 목표

1. **AI 기반 콘텐츠 생성**: LLM Agent를 활용하여 비즈니스에 맞는 마케팅 콘텐츠를 자동으로 생성
2. **멀티 플랫폼 관리**: 소셜 미디어, 블로그 등 다양한 플랫폼의 콘텐츠를 한 곳에서 관리
3. **자동 예약 발행**: 콘텐츠를 미리 작성하고 원하는 시간에 자동으로 발행
4. **브랜드 맞춤형**: 브랜드 분석을 통해 일관된 톤앤매너 유지
5. **성과 분석**: 콘텐츠 성과를 분석하고 인사이트 제공

---

## ✨ 핵심 기능

### 🤖 AI 콘텐츠 생성 (Multi-Agent Workflow)

**사용 시나리오: 카페 사장님이 "신메뉴 출시" 콘텐츠를 만든다면?**

1. 원하는 콘텐츠 생성 탭에서 "딸기 라떼 신메뉴 출시 홍보"라고 입력
2. 글 생성 
   - 📝 블로그 포스트 작성 (SEO 최적화)
   - 📷 Instagram 캡션 생성 (해시태그 포함)
   - ✍️ 이외에도 각 플랫폼 특성에 맞는 글 생성 
3. 이미지 생성 
    - 🎨 브랜드 DNA 반영한 AI 홍보 이미지 생성 (Nanobanana)
    - 🗞️ 배경 이미지 생성 통한 카드뉴스 (수정 및 생성, Nanobanana)
4. 영상 생성 
    - Multi-Agents가 자동으로:
        - 🎬 브랜드 DNA와 제품 특성에 맞는 스토리보드 생성
        - 🎨 스토리보드에 따른 컷 이미지 생성
        - 📹 frame-to-frame 통한 숏폼 동영상 생성
5. 🚀 7개 플랫폼에 생성된 홍보 콘텐츠 예약 발행

#### Multi-Agent Pipeline (영상 생성)

```
[사용자 입력: "신메뉴 홍보", 홍보 제품 이미지] 
         ↓
[VideoStoryboardOrchestrator] ← 전체 워크플로우 조정
    ├─ [ProductAnalysisAgent] ← 제품 이미지 분석 및 특징 추출 (1단계)
    ├─ [StoryPlanningAgent] ← 스토리 구조 선택 및 컷 배분 (2단계)
    ├─ [SceneDirectorAgent] ← 장면별 상세 연출 설계 (3단계)
    ├─ [QualityValidatorAgent] ← 품질 검증 및 자동 수정 (4단계)
    ├─ [ImageGenerationAgent] ← 이미지 생성 (Gemini 2.5 Flash Image / Gemini 3 Pro Image)
    ├─ [KlingVideoGenerationAgent] ← 동영상 생성 (fal.ai - Kling 2.1 Standard)
    └─ [VideoCompositionAgent] ← 최종 비디오 합성 (moviepy)
         ↓
[7개 플랫폼 동시 발행]
```

---

### 🎨 브랜드 분석 & 맞춤형 생성

**기존 SNS를 분석하여 브랜드 DNA를 자동 추출**

```
[Instagram/YouTube/Threads OAuth 연동 or 예시 콘텐츠 직접 입력]
         ↓
[BrandAnalysisPipeline] ← 전체 파이프라인 조정
    │
    ├─ Layer 1: Platform Collectors (병렬 수집)
    │   ├─ [InstagramCollectorAgent]
    │   ├─ [YouTubeCollectorAgent]
    │   └─ [ThreadsCollectorAgent]
    │
    ├─ Layer 2: Data Normalizer
    │   └─ [DataNormalizer] ← UnifiedContent로 정규화
    │
    ├─ Layer 3: Analysis Agents (병렬 분석)
    │   ├─ [TextAnalyzerAgent] ← 톤앤매너, 키워드, 해시태그
    │   ├─ [VisualAnalyzerAgent] ← 색상 팔레트, 비주얼 스타일
    │   └─ [EngagementAnalyzerAgent] ← 타겟 고객층, 참여 지표
    │
    └─ Layer 4: Brand Profile Synthesizer
        └─ [BrandProfileSynthesizer] ← 최종 브랜드 프로필 생성
             ↓
[모든 콘텐츠에 일관성 적용]
```

**분석 항목:**
- 📊 브랜드 톤앤매너 (친근함, 전문성, 유머 등)
- 🎨 색상 팔레트 및 비주얼 스타일
- 🔑 핵심 키워드 및 해시태그 패턴
- 👥 타겟 고객층 분석

---

### 📱 멀티 플랫폼 통합 발행

**한 번에 7개 플랫폼 동시 발행**

| 플랫폼 | 지원 기능 |
|--------|-----------|
| 📘 **Facebook** | 페이지 포스팅, 이미지/동영상 |
| 📸 **Instagram** | 피드, 릴스, 스토리 |
| 🎥 **YouTube** | 동영상 업로드, Shorts |
| 🐦 **X (Twitter)** | 트윗, 미디어 첨부 |
| 🧵 **Threads** | 텍스트 포스트 |
| 🎵 **TikTok** | 숏폼 동영상 |
| 📰 **WordPress** | 블로그 포스트 |

---



### 💬 AI 채팅 어시스턴트

대화형 인터페이스로 서비스 안내 및 콘텐츠 아이디어 발굴

- 자연어로 콘텐츠 요청
- 비즈니스 컨텍스트 자동 반영
- 채팅 히스토리 저장

---

## 🏗️ 시스템 아키텍처

### 전체 구조

```
[사용자]
    ↓
[React 19.2 Frontend]
    ↓ (REST API)
[FastAPI Backend]
    ↓
┌─────────────┬──────────────┬─────────────┐
│  Supabase   │  AI Services │ SNS APIs    │
│  PostgreSQL │  - Gemini    │ (7개)       │
│  Storage    │  - Vertex AI │             │
│             │  - fal.ai    │             │
└─────────────┴──────────────┴─────────────┘
```


### 데이터베이스 (36개 테이블)

| 카테고리 | 테이블 | 설명 |
|---------|--------|------|
| 사용자 | User, UserPreference | OAuth 정보, 스타일 설정 |
| 콘텐츠 | Content, GeneratedBlog, GeneratedSNS, GeneratedCardNews 등 | 생성 콘텐츠 관리 |
| 미디어 | GeneratedImage, GeneratedVideo, VideoGenerationJob | 이미지/동영상 저장 및 작업 관리 |
| 브랜드 | BrandAnalysis | 브랜드 프로필 |
| SNS 연동 | YouTubeConnection, InstagramConnection, ThreadsConnection, XConnection 등 | 플랫폼별 OAuth (7개 플랫폼) |
| 발행 추적 | PublishedContent | 통합 발행 이력 |
| 크레딧 | UserCredit, CreditTransaction | 사용량 관리 |
| 템플릿 | ContentTemplate | 콘텐츠 템플릿 |


---

## 🛠️ 기술 스택

| 영역 | 기술 |
|------|------|
| **Frontend** | React 19.2, Context API, Axios, React Router DOM |
| **Backend** | FastAPI, SQLAlchemy, Supabase (PostgreSQL) |
| **Database** | PostgreSQL (Supabase), Supabase Storage, 36개 테이블 |
| **AI/ML** | Google Gemini API, Vertex AI, fal.ai (Kling) |
| **External Services** | Google, Kakao, Facebook, Instagram, YouTube, X, Threads, TikTok, WordPress APIs |

---

## 📁 프로젝트 구조 요약


```
biz-content-agent/
├── backend/                    # FastAPI 백엔드
│   └── app/
│       ├── main.py             # 앱 설정 (36개 테이블)
│       ├── models.py, schemas.py, database.py
│       ├── auth.py, oauth.py   # 인증
│       ├── scheduler.py        # 예약 발행
│       │
│       ├── agents.py           # 카드뉴스 Multi-Agent
│       ├── video_agents.py     # 영상 생성 Multi-Agent
│       │
│       ├── routers/            # API 라우터 (23개)
│       │   ├── auth, user, chat, onboarding
│       │   ├── ai_content, image, cardnews, ai_video_generation
│       │   ├── brand_analysis, published_content, credits
│       │   └── sns/            # SNS 연동 (7개: YouTube, Instagram, Facebook, Threads, X, TikTok, WordPress)
│       │
│       ├── services/           # 비즈니스 로직
│       │   ├── ai_video_service.py, brand_analyzer_service.py
│       │   └── [SNS services]
│       │
│       ├── brand_agents/       # 브랜드 분석 Pipeline (6개 모듈)
│       │   └── pipeline, collectors, normalizer, analyzers, synthesizer, schemas
│       │
│       ├── prompts/            # AI 프롬프트
│       └── utils/              # 유틸리티
│
├── src/                        # React 프론트엔드
│   ├── pages/
│   │   ├── Home.js             # AI 채팅
│   │   ├── auth/, onboarding/, dashboard/
│   │   ├── content/            # 콘텐츠 생성/관리
│   │   │   ├── ContentHub, ContentCreator, ContentHistory
│   │   │   ├── ContentCreatorSimple.js  # 백업 파일
│   │   │   └── creator/        # 생성기 (Text, Image, Cardnews, Shortform)
│   │   ├── connection_SNS/     # SNS 연동 (7개 플랫폼)
│   │   └── credits/, settings/, profile/
│   │
│   ├── components/             # Layout, Sidebar, ProtectedRoute 등
│   └── contexts/               # Auth, Content, VideoJob, BrandAnalysis
│
└── .env.example                # 환경 변수 템플릿
```

---

## 🚀 시작하기

### 요구사항

- Node.js 18.x 이상
- Python 3.10 이상
- Supabase 계정 (PostgreSQL 데이터베이스)

### 빠른 시작

```bash
# 1. 저장소 클론
git clone https://github.com/YujinKi/biz-content-agent.git
cd biz-content-agent

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일 편집하여 API 키 입력 (아래 참고)

# 3. 프론트엔드 의존성 설치
npm install

# 4. 백엔드 설정
npm run setup:backend

# 5. 개발 서버 실행
npm start
```

**접속 주소:**
- 프론트엔드: http://localhost:3000
- 백엔드 API: http://localhost:8000
- API 문서: http://localhost:8000/docs

### 환경 변수 설정 (필수)

`.env` 파일에 다음 정보를 입력하세요:

```bash
# ===== Backend =====
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://postgres.YOUR_PROJECT_REF:YOUR_PASSWORD@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres

# ===== OAuth (선택 - 사용할 플랫폼만) =====
# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/oauth/google/callback
# Kakao OAuth
KAKAO_CLIENT_ID=your-kakao-rest-api-key
KAKAO_REDIRECT_URI=http://localhost:8000/api/oauth/kakao/callback
# Facebook OAuth
FACEBOOK_CLIENT_ID=your-facebook-app-id
FACEBOOK_CLIENT_SECRET=your-facebook-app-secret
FACEBOOK_REDIRECT_URI=http://localhost:8000/api/oauth/facebook/callback
# Instagram OAuth
INSTAGRAM_APP_ID=your-instagram-app-id
REACT_APP_INSTAGRAM_APP_ID=your-instagram-app-id
INSTAGRAM_REDIRECT_URI=http://localhost:8000/api/instagram/callback
# X (Twitter) OAuth
X_CLIENT_ID=your-x-client-id
X_CLIENT_SECRET=your-x-client-secret
X_REDIRECT_URI=http://127.0.0.1:8000/api/x/callback
# Threads OAuth
THREADS_APP_ID=your-threads-app-id
THREADS_APP_SECRET=your-threads-app-secret
THREADS_REDIRECT_URI=http://localhost:8000/api/threads/callback
# YouTube OAuth (Google OAuth 재사용)
YOUTUBE_REDIRECT_URI=http://localhost:8000/api/youtube/callback

# ===== AI API Keys (필수) =====
GOOGLE_API_KEY=your-google-api-key
REACT_APP_GEMINI_API_KEY=your-gemini-api-key
FAL_KEY=your-fal-api-key

# ===== Google Cloud (Vertex AI - 필수) =====
GOOGLE_CLOUD_PROJECT=your-google-cloud-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json

# ===== Supabase (필수) =====
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
```

### Supabase 데이터베이스 설정

1. [Supabase](https://supabase.com)에 접속하여 프로젝트 생성
2. Settings → Database에서 Connection string 복사
3. `.env` 파일의 `DATABASE_URL`에 붙여넣기

---

## 📚 주요 API 엔드포인트

### 인증
- `GET /api/auth/me` - 현재 사용자 정보
- `GET /api/oauth/{provider}/login` - OAuth 로그인 시작

### AI 콘텐츠
- `POST /api/chat` - AI 채팅
- `POST /api/ai-content/save` - 콘텐츠 저장
- `GET /api/ai-content/history` - 생성 이력

### 미디어 생성
- `POST /api/image/generate` - 이미지 생성
- `POST /api/ai-video/generate` - 동영상 생성
- `POST /api/cardnews/generate` - 카드뉴스 생성

### 브랜드 분석
- `POST /api/brand-analysis/analyze` - 브랜드 분석 실행
- `GET /api/brand-analysis/{user_id}` - 분석 결과 조회

### SNS 연동
- `POST /api/sns/publish` - 통합 SNS 발행
- `GET /api/youtube/connect` - YouTube 연동
- `GET /api/instagram/connect` - Instagram 연동

전체 API 문서: http://localhost:8000/docs

---

## 👥 팀원

| 이름 | 역할 | GitHub |
|------|------|--------|
| 기유진 | AI 개발, Backend | [@YujinKi](https://github.com/YujinKi) |
| 김종주 | Frontend, Backend | [@jonjour99](https://github.com/jonjour99) |
| 

### 프로젝트 정보

- **개발 기간:** 2025.11.13 ~ 2025.12.26
- **소속:** 커널 아카데미 AI 심화 과정

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🔗 관련 링크

- [API 문서](http://localhost:8000/docs) (로컬 실행 후)
- [Supabase](https://supabase.com)
- [Google Gemini API](https://ai.google.dev/gemini-api/docs)
- [fal.ai](https://fal.ai/)


