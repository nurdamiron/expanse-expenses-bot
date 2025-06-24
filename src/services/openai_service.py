import json
from typing import Optional, Dict
from openai import AsyncOpenAI

from src.core.config import settings


class OpenAIService:
    """Service for OpenAI API interactions"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
    
    async def parse_expense_text(self, prompt: str) -> Optional[Dict]:
        """Parse expense information from natural language using GPT"""
        if not self.client:
            return None
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts expense information from text. Always respond with valid JSON or null."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=150
            )
            
            content = response.choices[0].message.content.strip()
            
            # Handle null response
            if content.lower() == 'null':
                return None
            
            # Try to parse JSON
            try:
                result = json.loads(content)
                return result if isinstance(result, dict) else None
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code block
                if '```json' in content:
                    json_str = content.split('```json')[1].split('```')[0].strip()
                    result = json.loads(json_str)
                    return result if isinstance(result, dict) else None
                elif '```' in content:
                    json_str = content.split('```')[1].split('```')[0].strip()
                    result = json.loads(json_str)
                    return result if isinstance(result, dict) else None
                return None
                
        except Exception as e:
            print(f"OpenAI parsing error: {e}")
            return None