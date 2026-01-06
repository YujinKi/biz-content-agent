"""
Video Storyboard Generation Agents (4-Stage Pipeline)

Context Engineering 기반 4단계 Agent 파이프라인:
1. ProductAnalysisAgent: 제품 이미지 분석 및 특징 추출
2. StoryPlanningAgent: 스토리 구조 선택 및 컷 배분
3. SceneDirectorAgent: 장면별 상세 연출 설계
4. QualityValidatorAgent: 품질 검증 및 자동 수정

브랜드 프로필 신뢰도(confidence)에 따라 적용 강도 조절:
- high: 브랜드 가이드라인 엄격 준수
- medium: 참고하되 유연하게 적용
- low: 제품 이미지 분석 우선, 브랜드는 힌트만
"""

import os
import json
import base64
import httpx
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

import vertexai
from vertexai.generative_models import GenerativeModel as VertexGenerativeModel, Part
from sqlalchemy.orm import Session

from .models import VideoGenerationJob, User, BrandAnalysis
from .logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# 공통 유틸리티
# =============================================================================

async def download_and_encode_image(image_url: str) -> Dict[str, str]:
    """이미지 URL에서 다운로드하여 base64 인코딩"""

    if image_url.startswith(("http://", "https://")):
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "image/jpeg")
            media_type = content_type.split("/")[-1]
            image_content = response.content
    else:
        import mimetypes
        file_path = Path(__file__).parent.parent / image_url.lstrip("/")

        if not file_path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        image_content = file_path.read_bytes()
        mime_type, _ = mimetypes.guess_type(str(file_path))
        media_type = mime_type.split("/")[-1] if mime_type else "jpeg"

    image_base64 = base64.b64encode(image_content).decode("utf-8")

    return {
        "type": "base64",
        "media_type": f"image/{media_type}",
        "data": image_base64
    }


def image_data_to_vertex_part(image_data: Dict[str, str]) -> Part:
    """base64 이미지 데이터를 Vertex AI Part 객체로 변환"""
    from PIL import Image
    import io

    image_bytes = base64.b64decode(image_data["data"])
    pil_image = Image.open(io.BytesIO(image_bytes))

    img_byte_arr = io.BytesIO()
    pil_image.save(img_byte_arr, format='JPEG')
    img_bytes = img_byte_arr.getvalue()

    return Part.from_data(data=img_bytes, mime_type="image/jpeg")


def parse_json_response(response_text: str) -> Dict:
    """LLM 응답에서 JSON 추출 및 파싱"""
    if "```json" in response_text:
        json_start = response_text.find("```json") + 7
        json_end = response_text.find("```", json_start)
        response_text = response_text[json_start:json_end].strip()
    elif "```" in response_text:
        json_start = response_text.find("```") + 3
        json_end = response_text.find("```", json_start)
        response_text = response_text[json_start:json_end].strip()

    return json.loads(response_text)


def extract_brand_context(brand_analysis: Optional[BrandAnalysis]) -> Dict[str, Any]:
    """BrandAnalysis에서 필요한 정보 추출"""
    if not brand_analysis or not brand_analysis.brand_profile_json:
        return {
            "available": False,
            "confidence": "low"
        }

    profile = brand_analysis.brand_profile_json
    confidence = brand_analysis.profile_confidence or "low"

    return {
        "available": True,
        "confidence": confidence,
        "identity": profile.get("identity", {}),
        "tone_of_voice": profile.get("tone_of_voice", {}),
        "visual_style": profile.get("visual_style", {}),
        "content_strategy": profile.get("content_strategy", {}),
        "generation_prompts": profile.get("generation_prompts", {})
    }


def get_temporal_context() -> Dict[str, Any]:
    """현재 시간 기반 컨텍스트 생성 (시즌, 날씨, 이벤트 등)"""
    now = datetime.now()
    month = now.month
    day = now.day
    hour = now.hour
    weekday = now.strftime("%A")  # Monday, Tuesday, ...

    # 계절 판단 (한국 기준)
    if month in [3, 4, 5]:
        season = "spring"
        season_kr = "봄"
        weather_hint = "따뜻하고 화사한"
        color_mood = ["pastel pink", "light green", "soft yellow", "cherry blossom"]
    elif month in [6, 7, 8]:
        season = "summer"
        season_kr = "여름"
        weather_hint = "시원하고 청량한"
        color_mood = ["ocean blue", "bright white", "tropical green", "sunny yellow"]
    elif month in [9, 10, 11]:
        season = "autumn"
        season_kr = "가을"
        weather_hint = "따뜻하고 포근한"
        color_mood = ["warm orange", "burgundy", "golden brown", "deep red"]
    else:  # 12, 1, 2
        season = "winter"
        season_kr = "겨울"
        weather_hint = "따뜻하고 아늑한"
        color_mood = ["cozy beige", "warm white", "soft gray", "deep navy"]

    # 특별 시즌/이벤트 (마케팅 관점)
    special_events = []

    # 월별 이벤트
    if month == 1:
        special_events.append("새해/신년")
    elif month == 2:
        if 10 <= day <= 14:
            special_events.append("발렌타인데이")
    elif month == 3:
        if day == 14:
            special_events.append("화이트데이")
        if 1 <= day <= 8:
            special_events.append("삼일절/봄맞이")
    elif month == 4:
        special_events.append("벚꽃시즌")
    elif month == 5:
        if 1 <= day <= 5:
            special_events.append("어린이날")
        if 8 <= day <= 14:
            special_events.append("어버이날")
    elif month == 6:
        special_events.append("여름휴가준비")
    elif month == 7 or month == 8:
        special_events.append("휴가시즌/여름")
    elif month == 9:
        special_events.append("추석/한가위")
    elif month == 10:
        if 25 <= day <= 31:
            special_events.append("할로윈")
    elif month == 11:
        if 20 <= day <= 30:
            special_events.append("블랙프라이데이")
    elif month == 12:
        if day >= 20:
            special_events.append("크리스마스")
        special_events.append("연말/송년")

    # 시간대별 분위기
    if 6 <= hour < 10:
        time_mood = "morning"
        time_mood_kr = "아침"
        lighting_hint = "soft morning light, golden hour"
    elif 10 <= hour < 14:
        time_mood = "midday"
        time_mood_kr = "낮"
        lighting_hint = "bright natural daylight"
    elif 14 <= hour < 18:
        time_mood = "afternoon"
        time_mood_kr = "오후"
        lighting_hint = "warm afternoon light"
    elif 18 <= hour < 21:
        time_mood = "evening"
        time_mood_kr = "저녁"
        lighting_hint = "warm golden hour, sunset tones"
    else:
        time_mood = "night"
        time_mood_kr = "밤"
        lighting_hint = "cozy ambient lighting, soft warm indoor"

    return {
        "current_date": now.strftime("%Y-%m-%d"),
        "current_time": now.strftime("%H:%M"),
        "weekday": weekday,
        "season": season,
        "season_kr": season_kr,
        "month": month,
        "weather_hint": weather_hint,
        "seasonal_colors": color_mood,
        "special_events": special_events,
        "time_of_day": time_mood,
        "time_of_day_kr": time_mood_kr,
        "lighting_hint": lighting_hint
    }


# =============================================================================
# 1단계: 제품 분석 Agent
# =============================================================================

class ProductAnalysisAgent:
    """
    1단계: 제품 이미지와 정보를 분석하여 핵심 특징 추출

    입력: 제품 이미지, 제품명, 설명
    출력: 카테고리, 핵심 특징, 감정적 가치, 비주얼 정체성, 추천 스토리
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model

    async def analyze(
        self,
        image_data: Dict[str, str],
        product_name: str,
        product_description: Optional[str]
    ) -> Dict[str, Any]:
        """제품 분석 실행"""

        logger.info(f"[1단계] 제품 분석 시작: {product_name}")

        gemini_model = VertexGenerativeModel(self.model)
        image_part = image_data_to_vertex_part(image_data)

        prompt = f"""당신은 제품 마케팅 분석 전문가입니다.
제품 이미지와 정보를 분석하여 영상 제작에 필요한 핵심 정보를 추출하세요.

═══════════════════════════════════════
📦 분석할 제품 정보
═══════════════════════════════════════

제품명: {product_name}
제품 설명: {product_description or '제공되지 않음'}

═══════════════════════════════════════
🔍 분석 항목
═══════════════════════════════════════

다음 항목들을 분석하세요:

1. **제품 카테고리**
   - main: 대분류 (cosmetics / food / fashion / tech / lifestyle / other)
   - sub: 구체적인 제품 유형

2. **핵심 특징** (3-5개)
   - 이 제품만의 차별화된 특징
   - 마케팅에서 강조할 만한 포인트

3. **감정적 가치**
   - 이 제품이 고객에게 주는 감정적 혜택
   - 예: "자신감", "편안함", "특별한 순간", "일상의 활력"

4. **비주얼 정체성** (가장 중요!)
   - colors: 제품에서 보이는 주요 색상 3-5개 (영어)
   - texture: 질감 (glossy / matte / transparent / metallic / natural 등)
   - style: 비주얼 스타일 (luxury / casual / minimal / natural / modern 등)
   - lighting: 어울리는 조명 (bright / warm / cool / dramatic / soft natural 등)
   - key_elements: 눈에 띄는 디테일 (로고, 캡, 패키지 특징 등)

5. **추천 스토리 유형** (2-3개)
   - 이 제품에 어울리는 영상 스토리 구조
   - 선택지: Problem-Solution / Before-After / Process-Creation / Hero-Journey / Emotional-Arc / Lifestyle-Moment

═══════════════════════════════════════
📤 출력 형식 (JSON)
═══════════════════════════════════════

{{
  "category": {{
    "main": "대분류",
    "sub": "소분류"
  }},
  "key_features": [
    "특징 1",
    "특징 2",
    "특징 3"
  ],
  "emotional_value": "감정적 가치 설명",
  "visual_identity": {{
    "colors": ["color1", "color2", "color3"],
    "texture": "질감",
    "style": "스타일",
    "lighting": "조명 느낌",
    "key_elements": "핵심 시각 요소"
  }},
  "recommended_stories": ["추천1", "추천2"]
}}

다른 설명 없이 JSON만 반환하세요."""

        response = gemini_model.generate_content([prompt, image_part])
        result = parse_json_response(response.text)

        logger.info(f"[1단계] 제품 분석 완료: 카테고리={result.get('category', {}).get('main')}, 추천 스토리={result.get('recommended_stories', [])}")

        return result


# =============================================================================
# 2단계: 스토리 기획 Agent
# =============================================================================

class StoryPlanningAgent:
    """
    2단계: 최적의 스토리 구조 선택 및 컷 배분

    입력: 1단계 결과, 브랜드 프로필, 영상 스펙
    출력: 스토리 구조, 컷 배분, 톤 가이드라인, CTA 방식
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model

    async def plan(
        self,
        product_analysis: Dict[str, Any],
        brand_context: Dict[str, Any],
        cut_count: int,
        duration_seconds: int
    ) -> Dict[str, Any]:
        """스토리 기획 실행"""

        logger.info(f"[2단계] 스토리 기획 시작: {cut_count}컷, {duration_seconds}초")

        gemini_model = VertexGenerativeModel(self.model)

        # 브랜드 컨텍스트 프롬프트 구성
        brand_prompt = self._build_brand_prompt(brand_context)

        # 시간적 컨텍스트 생성
        temporal = get_temporal_context()
        temporal_prompt = self._build_temporal_prompt(temporal)

        prompt = f"""당신은 숏폼 영상 스토리텔링 전문가입니다.
제품 분석 결과와 브랜드 정보를 바탕으로 최적의 스토리 구조를 설계하세요.

═══════════════════════════════════════
📊 입력 정보
═══════════════════════════════════════

<product_analysis>
{json.dumps(product_analysis, ensure_ascii=False, indent=2)}
</product_analysis>

{brand_prompt}

{temporal_prompt}

<video_specs>
컷 수: {cut_count}개
총 길이: {duration_seconds}초
</video_specs>

═══════════════════════════════════════
🎬 선택 가능한 스토리 구조
═══════════════════════════════════════

1. **Problem-Solution** (문제-해결)
   - 적합: 기능성 제품, 생활용품, 건강식품
   - 흐름: 불편한 상황 → 제품 등장 → 해결 → 만족
   - 톤 조건: 격식도 50 이상일 때 효과적

2. **Before-After** (변화)
   - 적합: 화장품, 다이어트, 청소용품
   - 흐름: 사용 전 → 사용 중 → 사용 후 변화
   - 톤 조건: 열정도 60 이상일 때 효과적

3. **Process-Creation** (제작 과정)
   - 적합: 음식, 음료, 수제품, DIY
   - 흐름: 재료 → 만드는 과정 → 완성
   - 톤 조건: 따뜻함 60 이상일 때 효과적

4. **Hero-Journey** (제품의 여정)
   - 적합: 프리미엄 제품, 브랜드 스토리 강조
   - 흐름: 제품 소개 → 특별한 점 → 가치 전달
   - 톤 조건: 격식도 60 이상일 때 효과적

5. **Emotional-Arc** (감정 곡선)
   - 적합: 선물, 럭셔리, 감성 제품
   - 흐름: 감정 훅 → 감정 연결 → 클라이맥스 → 여운
   - 톤 조건: 따뜻함 70 이상일 때 효과적

6. **Lifestyle-Moment** (라이프스타일)
   - 적합: 패션, 액세서리, 일상용품
   - 흐름: 일상 속 순간 → 제품과 함께 → 완성된 라이프
   - 톤 조건: 격식도 40 이하, 따뜻함 60 이상일 때 효과적

═══════════════════════════════════════
📐 컷 배분 가이드
═══════════════════════════════════════

**4컷**: Hook(1) → 전개(2) → 클라이맥스(3) → CTA(4)
**6컷**: Hook(1) → 배경(2) → 전개(3-4) → 클라이맥스(5) → CTA(6)
**8컷**: Hook(1) → 배경(2) → 전개(3-5) → 클라이맥스(6-7) → CTA(8)

═══════════════════════════════════════
🎯 의사결정 기준
═══════════════════════════════════════

1. 제품 분석의 "recommended_stories"를 우선 고려
2. 브랜드 톤 수치가 해당 스토리의 조건에 맞는지 확인
3. 브랜드 신뢰도가 'low'면 제품 특성을 더 우선시
4. 타겟 고객과 감정적 톤이 스토리와 어울리는지 확인
5. **시간적 컨텍스트 활용**: 현재 시즌/이벤트에 맞는 분위기와 색감 반영

═══════════════════════════════════════
📤 출력 형식 (JSON)
═══════════════════════════════════════

{{
  "selected_structure": "선택한 스토리 구조명",
  "selection_reason": "이 구조를 선택한 이유 (2-3문장)",
  "seasonal_adaptation": {{
    "applied": true,
    "season_theme": "적용된 시즌 테마 (예: 크리스마스, 여름 휴가)",
    "mood_adjustment": "시즌에 맞게 조정된 분위기",
    "color_hints": ["시즌 컬러1", "시즌 컬러2"]
  }},
  "cut_allocation": [
    {{
      "cut": 1,
      "role": "이 컷의 역할 (예: Hook - 시선 끌기)",
      "story_function": "스토리에서 맡는 기능",
      "duration_ratio": 0.15,
      "is_hero_shot": true
    }},
    {{
      "cut": 2,
      "role": "역할",
      "story_function": "기능",
      "duration_ratio": 0.25,
      "is_hero_shot": false
    }}
  ],
  "tone_guidelines": {{
    "overall_mood": "전체 분위기 (시즌 반영)",
    "pacing": "빠름 / 중간 / 느림",
    "camera_style": "카메라 움직임 스타일",
    "transition_preference": "선호하는 전환 방식",
    "lighting_mood": "조명 분위기 (시간대 반영)"
  }},
  "cta_approach": "마지막 컷 CTA 방식"
}}

다른 설명 없이 JSON만 반환하세요."""

        response = gemini_model.generate_content(prompt)
        result = parse_json_response(response.text)

        logger.info(f"[2단계] 스토리 기획 완료: {result.get('selected_structure')}")

        return result

    def _build_brand_prompt(self, brand_context: Dict[str, Any]) -> str:
        """브랜드 컨텍스트를 프롬프트로 변환"""

        if not brand_context.get("available"):
            return """<brand_profile confidence="low">
브랜드 정보가 제공되지 않았습니다.
제품 분석 결과를 기반으로 스토리를 기획하세요.
</brand_profile>"""

        confidence = brand_context.get("confidence", "low")
        identity = brand_context.get("identity", {})
        tone = brand_context.get("tone_of_voice", {})
        strategy = brand_context.get("content_strategy", {})

        return f"""<brand_profile confidence="{confidence}">
[브랜드 정체성]
- 브랜드 성격: {identity.get('brand_personality', 'N/A')}
- 타겟 고객: {identity.get('target_audience', 'N/A')}
- 감정적 톤: {identity.get('emotional_tone', 'N/A')}

[톤 & 보이스 수치]
- 격식도: {tone.get('formality', 50)}/100 (0=매우 캐주얼, 100=매우 격식)
- 따뜻함: {tone.get('warmth', 50)}/100 (0=차가운, 100=따뜻한)
- 열정도: {tone.get('enthusiasm', 50)}/100 (0=차분한, 100=역동적)

[콘텐츠 전략]
- 주요 주제: {strategy.get('primary_topics', 'N/A')}
- CTA 스타일: {strategy.get('call_to_action_style', 'N/A')}

[신뢰도 적용 가이드]
- high: 위 정보를 엄격히 준수
- medium: 참고하되 제품 특성에 맞게 조절
- low: 제품 분석 우선, 위 정보는 힌트로만
</brand_profile>"""

    def _build_temporal_prompt(self, temporal: Dict[str, Any]) -> str:
        """시간적 컨텍스트를 프롬프트로 변환"""

        season_kr = temporal.get("season_kr", "")
        weather_hint = temporal.get("weather_hint", "")
        seasonal_colors = temporal.get("seasonal_colors", [])
        special_events = temporal.get("special_events", [])
        time_of_day_kr = temporal.get("time_of_day_kr", "")
        lighting_hint = temporal.get("lighting_hint", "")

        events_text = ", ".join(special_events) if special_events else "특별 이벤트 없음"
        colors_text = ", ".join(seasonal_colors) if seasonal_colors else "N/A"

        return f"""<temporal_context>
[현재 시점]
- 날짜: {temporal.get('current_date', 'N/A')}
- 계절: {season_kr}
- 시간대: {time_of_day_kr}

[시즌 분위기]
- 날씨/분위기: {weather_hint}
- 시즌 컬러: {colors_text}
- 특별 이벤트: {events_text}

[조명 힌트]
- 추천 조명: {lighting_hint}

[활용 가이드]
- 제품 특성에 맞다면 시즌 분위기를 스토리에 녹여주세요
- 특별 이벤트가 있다면 마케팅 관점에서 활용 고려
- 시즌 컬러는 배경/소품에 자연스럽게 반영
- 단, 제품 본연의 특성이 우선입니다
</temporal_context>"""


# =============================================================================
# 3단계: 장면 연출 Agent
# =============================================================================

class SceneDirectorAgent:
    """
    3단계: 각 컷의 상세 연출 설계 (이미지 프롬프트, 전환 효과)

    입력: 제품 이미지, 1-2단계 결과, 브랜드 비주얼 스타일
    출력: 완성된 스토리보드
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model

    async def design(
        self,
        image_data: Dict[str, str],
        product_analysis: Dict[str, Any],
        story_plan: Dict[str, Any],
        brand_context: Dict[str, Any],
        cut_count: int,
        duration_seconds: int
    ) -> List[Dict[str, Any]]:
        """장면 연출 설계 실행"""

        logger.info(f"[3단계] 장면 연출 설계 시작")

        gemini_model = VertexGenerativeModel(self.model)
        image_part = image_data_to_vertex_part(image_data)

        # 브랜드 비주얼 스타일 프롬프트 구성
        visual_style_prompt = self._build_visual_style_prompt(brand_context)

        # 타겟 캐릭터 정보
        target_info = self._build_target_character_prompt(brand_context)

        # 전환 타이밍 계산
        num_transitions = cut_count - 1
        avg_transition_duration = duration_seconds / num_transitions if num_transitions > 0 else 5.0
        cut_duration = 0.3

        prompt = f"""당신은 숏폼 영상 장면 연출 전문가입니다.
제품 이미지를 직접 보면서 각 컷의 상세한 연출을 설계하세요.

⚠️ 중요: 위 제품 이미지를 모든 컷에서 정확히 반영하세요.
- 제품의 형태, 색상, 질감, 로고, 디테일을 일관되게 유지
- 제품이 등장하는 모든 장면에서 동일한 제품으로 인식되어야 함

═══════════════════════════════════════
📊 입력 정보
═══════════════════════════════════════

<product_analysis>
{json.dumps(product_analysis, ensure_ascii=False, indent=2)}
</product_analysis>

<story_plan>
{json.dumps(story_plan, ensure_ascii=False, indent=2)}
</story_plan>

{visual_style_prompt}

{target_info}

<timing>
컷 수: {cut_count}개
총 길이: {duration_seconds}초
컷당 길이: {cut_duration}초 (고정)
전환 평균 길이: {avg_transition_duration:.1f}초
</timing>

═══════════════════════════════════════
🎨 공통 비주얼 설정 (중요!)
═══════════════════════════════════════

⚠️ **모든 컷에서 일관된 배경/조명/분위기를 유지하세요!**

먼저 shared_visual_context를 정의하고, 모든 컷이 이를 기반으로 작성되어야 합니다:
- primary_setting: 주요 배경 장소 (예: "modern minimalist kitchen", "cozy cafe interior")
- lighting_style: 일관된 조명 스타일 (예: "warm natural daylight from left")
- color_atmosphere: 전체 색감 분위기 (예: "warm beige and cream tones")
- consistent_props: 반복 등장할 소품들 (예: ["marble surface", "soft fabric napkin"])

**왜 중요한가?**
- 컷 1에서 2로 전환될 때 배경이 갑자기 바뀌면 영상이 어색해짐
- 카메라 구도와 제품 배치만 변경하고, 배경/조명/분위기는 일관되게 유지
- 예외: 스토리상 장소 이동이 필요한 경우에만 배경 변경 (명확한 이유 필요)

═══════════════════════════════════════
🎨 이미지 프롬프트 작성 규칙
═══════════════════════════════════════

⚠️ **필수: 모든 이미지는 9:16 세로 비율 (숏폼 최적화)**
- 구도 설계 시 세로 화면에 최적화된 배치 고려
- 제품이 화면 중앙~상단에 위치하도록 설계
- 세로 구도에서 시각적 균형 유지

모든 image_prompt는 영어로 작성하며, 다음 요소를 포함:

1. **주요 피사체**: 무엇이 화면에 있는지 (제품 외관 정확히 묘사)
2. **구도**: extreme close-up / close-up / medium shot / wide shot (9:16 세로 비율 기준)
3. **조명**: shared_visual_context.lighting_style과 일치
4. **배경**: shared_visual_context.primary_setting 기반 (구도에 따라 보이는 범위만 다름)
5. **분위기**: shared_visual_context.color_atmosphere와 일치
6. **제품 비주얼**: product_analysis의 visual_identity 요소 반드시 포함
7. **시즌 요소**: story_plan의 seasonal_adaptation.color_hints를 배경/소품에 자연스럽게 반영
8. **비율 명시**: 프롬프트 끝에 "vertical 9:16 aspect ratio" 추가

**시즌 반영 예시:**
- 겨울/크리스마스: "cozy beige backdrop with soft fairy lights, warm indoor ambiance"
- 여름: "bright white background with fresh green plants, refreshing summer vibes"
- 봄/벚꽃: "soft pink cherry blossom petals scattered, gentle spring atmosphere"

**일관된 배경의 프롬프트 예시 (컷 1→2→3):**
- 컷 1: "Strawberry cake on marble table, extreme close-up, warm natural lighting, cozy cafe interior with soft bokeh, cream and pink tones, vertical 9:16 aspect ratio"
- 컷 2: "Strawberry cake on marble table, medium shot showing cafe setting, warm natural lighting, cozy cafe interior with wooden chairs visible, cream and pink tones, vertical 9:16 aspect ratio"
- 컷 3: "Hand reaching for strawberry cake on marble table, close-up, warm natural lighting, cozy cafe interior, cream and pink tones, vertical 9:16 aspect ratio"
→ 배경(cafe interior, marble table), 조명(warm natural), 색감(cream and pink)이 일관됨

═══════════════════════════════════════
🎬 전환(Transition) 설계 규칙
═══════════════════════════════════════

**kling** (AI 영상 생성) - 다음 경우 사용:
- 실제 움직임 필요 (붓기, 섞기, 들기 등)
- 역동적 카메라 움직임 (줌인/아웃, 회전, 복잡한 패닝)
- 사람의 동작 포함
- 전체의 80-90% 사용 권장

**ffmpeg** (기본 효과) - 다음 경우 사용:
- 정적인 컷 사이 단순 전환
- 디졸브, 페이드 효과로 충분한 경우

**video_prompt 작성 주의:**
1. 사람 동작: 자연스럽게 (예: "casually picks up the bottle")
2. 재료 다루기: 도구 명시 (예: "using a long spoon to scoop")
3. 카메라: 구체적으로 (예: "Camera smoothly zooms out from close-up")

═══════════════════════════════════════
📤 출력 형식 (JSON)
═══════════════════════════════════════

{{
  "shared_visual_context": {{
    "primary_setting": "주요 배경 장소 (영어, 예: cozy cafe interior with warm ambiance)",
    "lighting_style": "일관된 조명 (영어, 예: warm natural daylight from window)",
    "color_atmosphere": "색감 분위기 (영어, 예: cream, soft pink, and gold tones)",
    "consistent_props": ["반복 소품1", "반복 소품2"],
    "setting_reason": "이 배경을 선택한 이유 (한국어, 1문장)"
  }},
  "storyboard": [
    {{
      "cut": 1,
      "scene_description": "장면 설명 (한국어, 2-3문장)",
      "story_role": "스토리에서의 역할",
      "image_prompt": "상세한 영어 이미지 프롬프트 (shared_visual_context 기반, 제품 비주얼 정확히 반영)",
      "duration": {cut_duration},
      "is_hero_shot": true,
      "resolution": "1080p",
      "needs_text": false
    }},
    {{
      "transition": {{
        "from_cut": 1,
        "to_cut": 2,
        "method": "kling",
        "effect": "dynamic_zoom_out",
        "video_prompt": "상세한 영어 비디오 프롬프트",
        "duration": {avg_transition_duration:.1f},
        "reason": "선택 이유"
      }}
    }},
    {{
      "cut": 2,
      "scene_description": "...",
      "story_role": "...",
      "image_prompt": "... (shared_visual_context의 배경/조명/색감 일관되게 유지)",
      "duration": {cut_duration},
      "is_hero_shot": false,
      "resolution": "720p",
      "needs_text": false
    }}
  ]
}}

⚠️ 모든 컷의 image_prompt는 shared_visual_context를 기반으로 작성하세요.
배경/조명/색감이 컷마다 달라지면 안 됩니다!

모든 {cut_count}개 컷과 {num_transitions}개 전환을 포함하세요.
다른 설명 없이 JSON만 반환하세요."""

        response = gemini_model.generate_content([prompt, image_part])
        result = parse_json_response(response.text)

        # shared_visual_context와 storyboard 추출
        shared_visual_context = result.get("shared_visual_context", {})
        storyboard_items = result.get("storyboard", result)
        if isinstance(storyboard_items, dict):
            storyboard_items = storyboard_items.get("storyboard", [])

        logger.info(f"[3단계] 장면 연출 완료: {len([s for s in storyboard_items if 'cut' in s])}컷 생성")
        if shared_visual_context:
            logger.info(f"[3단계] 공통 비주얼 설정: {shared_visual_context.get('primary_setting', 'N/A')}")

        # shared_visual_context와 storyboard를 함께 반환
        return {
            "shared_visual_context": shared_visual_context,
            "storyboard": storyboard_items
        }

    def _build_visual_style_prompt(self, brand_context: Dict[str, Any]) -> str:
        """브랜드 비주얼 스타일 프롬프트 구성"""

        confidence = brand_context.get("confidence", "low")
        visual_style = brand_context.get("visual_style", {})

        if not brand_context.get("available") or confidence == "low":
            return """<brand_visual_style confidence="low">
브랜드 비주얼 정보가 제한적입니다.
제품 이미지에서 추출한 visual_identity를 우선하세요.
</brand_visual_style>"""

        color_palette = visual_style.get("color_palette", [])
        image_style = visual_style.get("image_style", "N/A")
        composition = visual_style.get("composition_style", "N/A")

        apply_guide = "모든 컷에 반드시 포함" if confidence == "high" else "참고하되 제품에 맞게 조절"

        return f"""<brand_visual_style confidence="{confidence}">
[비주얼 요소]
- 색상 팔레트: {', '.join(color_palette) if color_palette else 'N/A'}
- 이미지 스타일: {image_style}
- 구도 스타일: {composition}

[적용 가이드]
{apply_guide}
</brand_visual_style>"""

    def _build_target_character_prompt(self, brand_context: Dict[str, Any]) -> str:
        """타겟 캐릭터 정보 프롬프트 구성"""

        identity = brand_context.get("identity", {})
        target = identity.get("target_audience", "")

        if not target:
            return """<target_character>
타겟 정보 없음. 사람이 등장하는 경우 한국인으로 설정.
</target_character>"""

        return f"""<target_character>
타겟 고객: {target}
→ 사람이 등장하는 컷에서 반드시 반영:
   - 국적: 한국인 (Korean)
   - 성별/나이: 타겟과 일치
   - 외모: 자연스러운 한국인 외모
</target_character>"""


# =============================================================================
# 4단계: 품질 검증 Agent
# =============================================================================

class QualityValidatorAgent:
    """
    4단계: 브랜드 일관성 및 품질 검증, 자동 수정

    2단계 분리 구조:
    1. evaluate(): 평가만 수행 (빠름) - 스토리보드 재생성 없음
    2. fix_issues(): 실패 시에만 문제 컷 수정 (필요할 때만 호출)

    입력: 제품 이미지, 3단계 스토리보드, 1단계 분석, 브랜드 프로필
    출력: 평가 점수, (필요시) 수정된 스토리보드
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model

    async def evaluate(
        self,
        image_data: Dict[str, str],
        storyboard: List[Dict[str, Any]],
        product_analysis: Dict[str, Any],
        brand_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """1단계: 평가만 수행 (스토리보드 재생성 없음)"""

        logger.info(f"[4단계] 품질 평가 시작")

        gemini_model = VertexGenerativeModel(self.model)
        image_part = image_data_to_vertex_part(image_data)

        confidence = brand_context.get("confidence", "low")

        prompt = f"""당신은 브랜드 콘텐츠 품질 검증 전문가입니다.
제품 이미지를 직접 보면서 스토리보드가 제품을 정확히 반영하는지 검증하세요.

⚠️ 핵심 검증: 위 제품 이미지와 각 컷의 image_prompt가 일치하는지 확인

═══════════════════════════════════════
📊 검증 대상
═══════════════════════════════════════

<storyboard>
{json.dumps(storyboard, ensure_ascii=False, indent=2)}
</storyboard>

<product_visual_identity>
{json.dumps(product_analysis.get('visual_identity', {}), ensure_ascii=False, indent=2)}
</product_visual_identity>

<brand_context confidence="{confidence}">
{json.dumps({
    'identity': brand_context.get('identity', {}),
    'visual_style': brand_context.get('visual_style', {}),
    'tone_of_voice': brand_context.get('tone_of_voice', {})
}, ensure_ascii=False, indent=2)}
</brand_context>

═══════════════════════════════════════
✅ 검증 항목 (각 10점 만점)
═══════════════════════════════════════

**1. 스토리 일관성 (story_coherence)**
- 전체 흐름이 자연스러운가?
- 선택한 스토리 구조가 잘 지켜졌는가?

**2. 비주얼 일관성 (visual_consistency)** ⭐ 가장 중요
- 제품 이미지의 색상, 형태, 질감이 모든 image_prompt에 정확히 반영되었는가?
- 제품의 key_elements(로고, 캡, 디테일)가 언급되었는가?
- **배경 일관성**: shared_visual_context가 모든 컷에 일관되게 적용되었는가?
  - 배경 장소(primary_setting)가 컷마다 갑자기 바뀌지 않는가?
  - 조명 스타일(lighting_style)이 일관되는가?
  - 색감 분위기(color_atmosphere)가 일관되는가?

**3. 브랜드 적합성 (brand_fit)**
- 신뢰도 {confidence}: {"브랜드 가이드라인 엄격 준수 필요" if confidence == "high" else "참고 수준으로 확인" if confidence == "medium" else "제품 중심으로 확인"}
- 브랜드 색상/톤이 반영되었는가?

**4. 기술적 완성도 (technical_quality)**
- image_prompt가 충분히 상세한가?
- video_prompt에 카메라/동작이 명확한가?

**5. 마케팅 효과 (marketing_effectiveness)**
- 첫 컷이 시선을 끄는가?
- 제품 특징이 잘 드러나는가?
- CTA가 효과적인가?

═══════════════════════════════════════
📤 출력 형식 (JSON) - 평가만, 스토리보드 재생성 없음
═══════════════════════════════════════

{{
  "evaluation": {{
    "story_coherence": {{ "score": 8, "comment": "간단한 평가" }},
    "visual_consistency": {{ "score": 7, "comment": "간단한 평가" }},
    "brand_fit": {{ "score": 9, "comment": "간단한 평가" }},
    "technical_quality": {{ "score": 8, "comment": "간단한 평가" }},
    "marketing_effectiveness": {{ "score": 8, "comment": "간단한 평가" }},
    "total_score": 8.0
  }},
  "issues": [
    {{
      "cut": 3,
      "field": "image_prompt",
      "issue": "문제 설명",
      "suggested_fix": "수정 제안"
    }}
  ],
  "summary": "검증 결과 요약 (1문장)"
}}

**중요**: corrected_storyboard는 반환하지 마세요. 평가와 issues만 반환하세요.
다른 설명 없이 JSON만 반환하세요."""

        response = gemini_model.generate_content([prompt, image_part])
        result = parse_json_response(response.text)

        total_score = result.get("evaluation", {}).get("total_score", 0)
        visual_score = result.get("evaluation", {}).get("visual_consistency", {}).get("score", 0)

        logger.info(f"[4단계] 품질 평가 완료: 총점={total_score}, 비주얼={visual_score}")

        return result

    async def fix_issues(
        self,
        image_data: Dict[str, str],
        storyboard: List[Dict[str, Any]],
        issues: List[Dict[str, Any]],
        product_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """2단계: 문제가 있는 컷만 수정 (실패 시에만 호출)"""

        if not issues:
            return storyboard

        logger.info(f"[4단계] 스토리보드 수정 시작: {len(issues)}개 이슈")

        gemini_model = VertexGenerativeModel(self.model)
        image_part = image_data_to_vertex_part(image_data)

        # 문제가 있는 컷 번호 추출
        problem_cuts = set(issue.get("cut") for issue in issues if issue.get("cut"))

        prompt = f"""당신은 스토리보드 수정 전문가입니다.
아래 issues에 명시된 문제를 해결하여 수정된 스토리보드를 반환하세요.

═══════════════════════════════════════
📊 원본 스토리보드
═══════════════════════════════════════

{json.dumps(storyboard, ensure_ascii=False, indent=2)}

═══════════════════════════════════════
⚠️ 수정이 필요한 이슈
═══════════════════════════════════════

{json.dumps(issues, ensure_ascii=False, indent=2)}

═══════════════════════════════════════
🎨 제품 비주얼 (참고)
═══════════════════════════════════════

{json.dumps(product_analysis.get('visual_identity', {}), ensure_ascii=False, indent=2)}

═══════════════════════════════════════
📤 출력 형식
═══════════════════════════════════════

수정된 전체 스토리보드를 JSON 배열로 반환하세요.
- 문제가 있는 컷({', '.join(str(c) for c in problem_cuts)})만 수정
- 나머지 컷과 transition은 원본 그대로 유지
- 다른 설명 없이 JSON 배열만 반환"""

        response = gemini_model.generate_content([prompt, image_part])
        result = parse_json_response(response.text)

        # 결과가 리스트인지 확인
        if isinstance(result, list):
            corrected = result
        elif isinstance(result, dict) and "storyboard" in result:
            corrected = result["storyboard"]
        else:
            logger.warning("수정된 스토리보드 파싱 실패, 원본 사용")
            return storyboard

        logger.info(f"[4단계] 스토리보드 수정 완료: {len(corrected)}개 항목")
        return corrected

    async def validate(
        self,
        image_data: Dict[str, str],
        storyboard: List[Dict[str, Any]],
        product_analysis: Dict[str, Any],
        brand_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """기존 호환성 유지: evaluate + fix_issues 통합 호출"""
        # 먼저 평가만 수행
        eval_result = await self.evaluate(
            image_data=image_data,
            storyboard=storyboard,
            product_analysis=product_analysis,
            brand_context=brand_context
        )

        # 결과에 corrected_storyboard 추가 (빈 배열)
        eval_result["corrected_storyboard"] = []

        return eval_result


# =============================================================================
# 통합 오케스트레이터
# =============================================================================

class VideoStoryboardOrchestrator:
    """
    4단계 Agent 파이프라인 통합 관리

    - 순차적 실행
    - 4단계 실패 시 최대 3회 재시도
    - 최종 스토리보드 반환
    """

    def __init__(self):
        self.product_agent = ProductAnalysisAgent()
        self.story_agent = StoryPlanningAgent()
        self.scene_agent = SceneDirectorAgent()
        self.quality_agent = QualityValidatorAgent()
        self.max_retries = 3

    async def generate_storyboard(
        self,
        job: VideoGenerationJob,
        user: User,
        brand_analysis: Optional[BrandAnalysis],
        db: Session
    ) -> List[Dict[str, Any]]:
        """4단계 파이프라인 실행"""

        logger.info(f"═══════════════════════════════════════")
        logger.info(f"🎬 Video Storyboard Generation 시작 (Job ID: {job.id})")
        logger.info(f"═══════════════════════════════════════")

        start_time = time.time()
        generation_attempts = 0

        try:
            # 제품 이미지 로드
            job.status = "analyzing_product"
            job.current_step = "제품 이미지 로딩 중"
            db.commit()

            image_data = await download_and_encode_image(job.uploaded_image_url)

            # 브랜드 컨텍스트 추출
            brand_context = extract_brand_context(brand_analysis)
            brand_confidence = brand_context.get('confidence', 'low')
            logger.info(f"브랜드 신뢰도: {brand_confidence}")

            # 브랜드 신뢰도 저장
            job.brand_confidence_used = brand_confidence
            db.commit()

            # ─────────────────────────────────────
            # 1단계: 제품 분석
            # ─────────────────────────────────────
            job.current_step = "1단계: 제품 분석 중"
            db.commit()

            product_analysis = await self.product_agent.analyze(
                image_data=image_data,
                product_name=job.product_name,
                product_description=job.product_description
            )

            # 1단계 결과 저장
            job.product_analysis = product_analysis
            db.commit()
            logger.info(f"[DB 저장] 1단계 제품 분석 결과 저장 완료")

            # ─────────────────────────────────────
            # 2단계: 스토리 기획
            # ─────────────────────────────────────
            job.status = "planning_story"
            job.current_step = "2단계: 스토리 기획 중"
            db.commit()

            story_plan = await self.story_agent.plan(
                product_analysis=product_analysis,
                brand_context=brand_context,
                cut_count=job.cut_count,
                duration_seconds=job.duration_seconds
            )

            # 2단계 결과 저장
            job.story_plan = story_plan
            db.commit()
            logger.info(f"[DB 저장] 2단계 스토리 기획 결과 저장 완료")

            # ─────────────────────────────────────
            # 3단계: 장면 연출
            # ─────────────────────────────────────
            job.status = "designing_scenes"
            job.current_step = "3단계: 장면 연출 설계 중"
            db.commit()

            scene_result = await self.scene_agent.design(
                image_data=image_data,
                product_analysis=product_analysis,
                story_plan=story_plan,
                brand_context=brand_context,
                cut_count=job.cut_count,
                duration_seconds=job.duration_seconds
            )

            # 새 구조: {shared_visual_context: {...}, storyboard: [...]}
            shared_visual_context = scene_result.get("shared_visual_context", {})
            storyboard = scene_result.get("storyboard", scene_result if isinstance(scene_result, list) else [])

            # ─────────────────────────────────────
            # 4단계: 품질 검증 (2단계 분리 구조)
            # ─────────────────────────────────────
            job.status = "validating_quality"
            validation_result = None

            for attempt in range(1, self.max_retries + 1):
                generation_attempts = attempt
                job.current_step = f"4단계: 품질 검증 중 (시도 {attempt}/{self.max_retries})"
                job.generation_attempts = attempt
                db.commit()

                # 1단계: 평가만 수행 (빠름 - 스토리보드 재생성 없음)
                validation_result = await self.quality_agent.evaluate(
                    image_data=image_data,
                    storyboard=storyboard,
                    product_analysis=product_analysis,
                    brand_context=brand_context
                )

                evaluation = validation_result.get("evaluation", {})
                total_score = evaluation.get("total_score", 0)
                visual_score = evaluation.get("visual_consistency", {}).get("score", 0)
                issues = validation_result.get("issues", [])

                logger.info(f"검증 결과 (시도 {attempt}): 총점={total_score}, 비주얼={visual_score}, 이슈={len(issues)}개")

                # 통과 조건: 점수 기반 판단
                # - 총점 7.5점 이상 AND 비주얼 일관성 6.5점 이상
                if total_score >= 7.5 and visual_score >= 6.5:
                    logger.info(f"✅ 품질 검증 통과!")
                    break

                # 2단계: 실패 시에만 문제 컷 수정 (issues 기반)
                if issues and attempt < self.max_retries:
                    logger.info(f"🔧 이슈 기반 스토리보드 수정 시작")
                    storyboard = await self.quality_agent.fix_issues(
                        image_data=image_data,
                        storyboard=storyboard,
                        issues=issues,
                        product_analysis=product_analysis
                    )

                if attempt == self.max_retries:
                    logger.warning(f"⚠️ 최대 재시도 횟수 도달, 현재 스토리보드 사용")

            # 4단계 품질 평가 결과 저장
            if validation_result:
                job.quality_evaluation = {
                    "evaluation": validation_result.get("evaluation", {}),
                    "issues": validation_result.get("issues", []),
                    "summary": validation_result.get("summary", ""),
                    "final_attempt": generation_attempts
                }
                db.commit()
                logger.info(f"[DB 저장] 4단계 품질 검증 결과 저장 완료")

            # ─────────────────────────────────────
            # 완료 및 메타데이터 저장
            # ─────────────────────────────────────
            processing_time = time.time() - start_time
            job.processing_time_seconds = processing_time
            job.generation_attempts = generation_attempts
            db.commit()

            logger.info(f"═══════════════════════════════════════")
            logger.info(f"✅ Storyboard Generation 완료 (Job ID: {job.id})")
            logger.info(f"   - 컷 수: {len([s for s in storyboard if 'cut' in s])}")
            logger.info(f"   - 전환 수: {len([s for s in storyboard if 'transition' in s])}")
            logger.info(f"   - 공통 배경: {shared_visual_context.get('primary_setting', 'N/A')}")
            logger.info(f"   - 재시도 횟수: {generation_attempts}")
            logger.info(f"   - 처리 시간: {processing_time:.1f}초")
            logger.info(f"═══════════════════════════════════════")

            # shared_visual_context와 storyboard를 함께 반환 (DB 저장용)
            return {
                "shared_visual_context": shared_visual_context,
                "storyboard": storyboard
            }

        except Exception as e:
            # 오류 발생 시에도 처리 시간 저장
            processing_time = time.time() - start_time
            job.processing_time_seconds = processing_time
            job.generation_attempts = generation_attempts
            db.commit()

            import traceback
            error_detail = str(e) if str(e) else repr(e)
            logger.error(f"❌ Storyboard Generation 실패: {error_detail}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
