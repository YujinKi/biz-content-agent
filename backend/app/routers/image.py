from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx
import os
from typing import Optional
from ..logger import get_logger
from ..database import get_db
from ..models import BrandAnalysis

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["image"]
)


class ImageGenerateRequest(BaseModel):
    prompt: str
    model: str = "nanobanana"
    referenceImage: Optional[str] = None  # Base64 encoded image for image-to-image
    userId: Optional[int] = None  # 사용자 ID (브랜드 분석 정보 조회용)
    aspect_ratio: Optional[str] = "1:1"  # 이미지 비율 (예: '1:1', '4:5', '9:16', '16:9')


class ImageGenerateResponse(BaseModel):
    success: bool
    imageUrl: str
    optimizedPrompt: Optional[str] = None
    usedNanobananaAPI: bool = False
    usedBrandAnalysis: bool = False


def get_brand_analysis(db: Session, user_id: int) -> Optional[BrandAnalysis]:
    """사용자의 브랜드 분석 정보 조회"""
    return db.query(BrandAnalysis).filter(BrandAnalysis.user_id == user_id).first()


async def convert_to_visual_prompt(prompt: str, google_api_key: str) -> str:
    """
    사용자의 텍스트 주제를 이미지 생성에 적합한 시각적 설명으로 변환
    예: "우리 카페 신메뉴 아이스 아메리카노 출시!" -> "A beautiful iced americano coffee in a clear glass..."
    """
    try:
        conversion_prompt = f"""You are an expert at converting text topics into visual image prompts.

Given this topic/message: "{prompt}"

Convert it to a detailed English visual description for AI image generation.
Focus ONLY on describing visual elements that can be depicted in a photograph or illustration:
- Objects, products, scenes, settings
- Colors, lighting, mood, atmosphere
- Composition, angles, style
- DO NOT include any text, words, slogans, or typography in your description
- DO NOT mention that text should be included
- Focus on pure visual elements only

Output ONLY the visual prompt in English, nothing else. Keep it under 150 words."""

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={google_api_key}",
                json={
                    "contents": [{"parts": [{"text": conversion_prompt}]}]
                },
                headers={"Content-Type": "application/json"}
            )

        if response.status_code == 200:
            data = response.json()
            if data.get("candidates") and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                if candidate.get("content") and candidate["content"].get("parts"):
                    visual_prompt = candidate["content"]["parts"][0].get("text", "").strip()
                    if visual_prompt:
                        logger.info(f"프롬프트 변환 완료: {prompt[:30]}... -> {visual_prompt[:50]}...")
                        return visual_prompt

        # 변환 실패 시 원본 반환
        logger.warning("프롬프트 변환 실패, 원본 사용")
        return prompt
    except Exception as e:
        logger.warning(f"프롬프트 변환 중 오류: {e}, 원본 사용")
        return prompt


def get_aspect_ratio_instruction(aspect_ratio: str) -> str:
    """비율에 따른 이미지 생성 지시문 반환"""
    ratio_map = {
        "1:1": "square format (1:1 aspect ratio)",
        "4:5": "portrait format (4:5 aspect ratio, ideal for Instagram posts)",
        "9:16": "vertical format (9:16 aspect ratio, ideal for Stories/Reels)",
        "16:9": "landscape format (16:9 aspect ratio, ideal for YouTube thumbnails)",
    }
    return ratio_map.get(aspect_ratio, "square format (1:1 aspect ratio)")


def enhance_prompt_with_brand(prompt: str, brand_analysis: BrandAnalysis) -> str:
    """브랜드 분석 정보를 프롬프트에 반영"""
    brand_elements = []

    # emotional_tone: 감정적 톤 (예: 따뜻한, 유머러스한)
    if brand_analysis.emotional_tone:
        brand_elements.append(f"emotional mood: {brand_analysis.emotional_tone}")

    # brand_personality: 브랜드 성격 종합 설명
    if brand_analysis.brand_personality:
        # 너무 길면 요약
        personality = brand_analysis.brand_personality[:100] if len(brand_analysis.brand_personality) > 100 else brand_analysis.brand_personality
        brand_elements.append(f"brand personality: {personality}")

    # brand_tone: 브랜드 톤앤매너 (예: 친근하고 전문적인)
    if brand_analysis.brand_tone:
        brand_elements.append(f"style tone: {brand_analysis.brand_tone}")

    # 인스타그램 이미지 스타일이 있으면 추가
    if brand_analysis.instagram_image_style:
        brand_elements.append(f"visual style: {brand_analysis.instagram_image_style}")

    # 색상 팔레트가 있으면 추가
    if brand_analysis.instagram_color_palette:
        colors = ", ".join(brand_analysis.instagram_color_palette[:3])  # 최대 3개 색상
        brand_elements.append(f"color palette: {colors}")

    if brand_elements:
        brand_context = ", ".join(brand_elements)
        enhanced_prompt = f"{prompt}. Brand context: {brand_context}"
        return enhanced_prompt

    return prompt


@router.post("/generate-image", response_model=ImageGenerateResponse)
async def generate_image(request: ImageGenerateRequest, db: Session = Depends(get_db)):
    """
    이미지 생성 엔드포인트
    - model: 'nanobanana' (Gemini 2.5 Flash Image)
    - userId: 사용자 ID를 전달하면 브랜드 분석 정보가 이미지 생성에 반영됩니다.
    """
    if not request.prompt:
        raise HTTPException(status_code=400, detail="프롬프트가 필요합니다.")

    try:
        used_nanobanana_api = False
        used_brand_analysis = False
        image_url = None
        enhanced_prompt = request.prompt  # 기본값 설정

        # 브랜드 분석 정보 조회
        brand_analysis = None
        if request.userId:
            brand_analysis = get_brand_analysis(db, request.userId)
            if brand_analysis:
                print(f"🏷️ 브랜드 분석 정보 발견!")
                print(f"   - emotional_tone: {brand_analysis.emotional_tone}")
                print(f"   - brand_personality: {brand_analysis.brand_personality[:50] if brand_analysis.brand_personality else 'N/A'}...")
                print(f"   - brand_tone: {brand_analysis.brand_tone}")
                used_brand_analysis = True

        # Nanobanana (Gemini 2.5 Flash Image)
        if request.model == "nanobanana":
            google_api_key = os.getenv('REACT_APP_GEMINI_API_KEY')
            if not google_api_key:
                raise HTTPException(
                    status_code=500,
                    detail="Google API 키가 필요합니다. (Gemini 2.5 Flash Image)"
                )

            # 1단계: 사용자 프롬프트를 시각적 설명으로 변환 (한국어 -> 영어 시각적 프롬프트)
            visual_prompt = await convert_to_visual_prompt(request.prompt, google_api_key)
            print(f"🎨 시각적 프롬프트 변환: {request.prompt[:30]}... -> {visual_prompt[:50]}...")

            # 2단계: 브랜드 분석 정보가 있으면 프롬프트 강화
            enhanced_prompt = visual_prompt
            if brand_analysis:
                enhanced_prompt = enhance_prompt_with_brand(visual_prompt, brand_analysis)
                print(f"🏷️ 브랜드 반영 프롬프트: {enhanced_prompt}")

            # 재시도 로직 추가 (최대 3회)
            max_retries = 3
            last_error = None

            for attempt in range(max_retries):
                try:
                    # 레퍼런스 이미지가 있는지 확인
                    if request.referenceImage:
                        logger.info("Nanobanana (Gemini 2.5 Flash) Image-to-Image 생성 시작")
                        logger.debug(f"프롬프트: {request.prompt}")
                        logger.debug("레퍼런스 이미지 사용")

                        # Base64에서 data:image/...;base64, 접두사 제거
                        ref_image_data = request.referenceImage
                        if ',' in ref_image_data:
                            ref_image_data = ref_image_data.split(',')[1]

                        # 요청에 레퍼런스 이미지 포함
                        request_body = {
                            "contents": [{
                                "parts": [
                                    {
                                        "inline_data": {
                                            "mime_type": "image/jpeg",
                                            "data": ref_image_data
                                        }
                                    },
                                    {
                                        "text": f"Based on this reference image, generate a new image: {enhanced_prompt}. IMPORTANT: Do NOT include any text, letters, words, numbers, watermarks, or typography in the generated image."
                                    }
                                ]
                            }]
                        }
                    else:
                        print(f"🍌 나노바나나(Gemini 2.5 Flash Image - Text-to-Image)로 이미지 생성 중... (시도 {attempt + 1}/{max_retries})")
                        print(f"📝 받은 프롬프트: {request.prompt}")
                        print(f"📐 이미지 비율: {request.aspect_ratio}")

                        # 비율 지시문 가져오기
                        aspect_instruction = get_aspect_ratio_instruction(request.aspect_ratio)

                        # 텍스트만 사용 - 이미지 내 텍스트 삽입 금지 명시 + 비율 정보 포함
                        request_body = {
                            "contents": [{
                                "parts": [{
                                    "text": f"Create a high-quality image in {aspect_instruction}: {enhanced_prompt}. IMPORTANT: Do NOT include any text, letters, words, numbers, watermarks, or typography in the generated image. The image should be purely visual without any written content."
                                }]
                            }],
                            "generationConfig": {
                                "responseModalities": ["image", "text"]
                            }
                        }

                    async with httpx.AsyncClient(timeout=180.0) as client:
                        response = await client.post(
                            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key={google_api_key}",
                            json=request_body,
                            headers={"Content-Type": "application/json"}
                        )

                    if response.status_code != 200:
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"Gemini API 오류: {response.text}"
                        )

                    data = response.json()

                    # 디버깅: API 응답 구조 확인
                    logger.debug(f"Gemini API 응답 구조: {list(data.keys())}")
                    if data.get("candidates"):
                        logger.debug(f"Candidates 수: {len(data['candidates'])}")
                        if len(data["candidates"]) > 0:
                            candidate = data["candidates"][0]
                            logger.debug(f"첫 번째 candidate 키: {list(candidate.keys())}")
                            if candidate.get("content"):
                                logger.debug(f"Content 키: {list(candidate['content'].keys())}")
                                if candidate["content"].get("parts"):
                                    logger.debug(f"Parts 수: {len(candidate['content']['parts'])}")
                                    for i, part in enumerate(candidate["content"]["parts"]):
                                        logger.debug(f"Part {i} 키: {list(part.keys())}")

                    # 응답에서 이미지 추출
                    if data.get("candidates") and len(data["candidates"]) > 0:
                        candidate = data["candidates"][0]

                        if candidate.get("content") and candidate["content"].get("parts"):
                            for part in candidate["content"]["parts"]:
                                # Gemini API는 camelCase를 사용 (inlineData)
                                if part.get("inlineData") and part["inlineData"].get("data"):
                                    mime_type = part["inlineData"].get("mimeType", "image/png")
                                    image_data = part["inlineData"]["data"]
                                    image_url = f"data:{mime_type};base64,{image_data}"
                                    break

                    if image_url:
                        # 이미지 추출 성공
                        break
                    else:
                        last_error = "Gemini API로부터 이미지를 추출하지 못했습니다."
                        logger.warning(f"이미지 추출 실패 (시도 {attempt + 1}/{max_retries}): {data}")
                        if attempt < max_retries - 1:
                            import asyncio
                            await asyncio.sleep(1)  # 1초 대기 후 재시도

                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"이미지 생성 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        import asyncio
                        await asyncio.sleep(1)

            if not image_url:
                logger.error(f"모든 재시도 실패: {last_error}")
                raise HTTPException(
                    status_code=500,
                    detail=f"이미지 생성 실패: {last_error}"
                )

            used_nanobanana_api = True
            logger.info("Nanobanana 이미지 생성 완료")

        else:
            raise HTTPException(
                status_code=400,
                detail="지원하지 않는 AI 모델입니다. 'nanobanana'만 지원됩니다."
            )

        return ImageGenerateResponse(
            success=True,
            imageUrl=image_url,
            optimizedPrompt=enhanced_prompt if enhanced_prompt != request.prompt else None,
            usedNanobananaAPI=used_nanobanana_api,
            usedBrandAnalysis=used_brand_analysis
        )

    except HTTPException:
        raise
    except httpx.TimeoutException:
        logger.error("이미지 생성 요청 시간 초과")
        raise HTTPException(
            status_code=504,
            detail="요청 시간이 초과되었습니다."
        )
    except Exception as e:
        logger.error(f"이미지 생성 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"이미지 생성 중 오류가 발생했습니다: {str(e)}"
        )
