# core/ai_service.py
import requests
import json
import logging
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

class DeepSeekAIService:
    """Central AI service for all apps"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'DEEPSEEK_API_KEY', None)
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        
        if not self.api_key:
            logger.warning("⚠️ DeepSeek API key not configured")
    
    # ==========================================
    # REAL ESTATE AI FUNCTIONS
    # ==========================================
    
    def analyze_property(self, property_obj):
        """Analyze property with AI"""
        if not self.api_key:
            return {"error": "DeepSeek API key not configured"}
        
        property_data = {
            "title": property_obj.title,
            "description": property_obj.description[:500] if property_obj.description else "",
            "city": property_obj.city,
            "country": property_obj.country,
            "price": str(property_obj.base_price) if property_obj.base_price else "N/A",
            "bedrooms": property_obj.bedrooms,
            "bathrooms": property_obj.bathrooms,
            "status": property_obj.status,
            "listing_type": property_obj.listing_type,
        }
        
        bookings = property_obj.bookings.all()
        property_data["total_bookings"] = bookings.count()
        
        prompt = f"""
        Analyze this property and provide insights in JSON format:
        
        Property Details:
        {json.dumps(property_data, indent=2)}
        
        Return JSON with:
        - summary: (string) Brief summary
        - selling_points: (array) Key selling points
        - target_audience: (string) Who should buy/rent
        - price_assessment: (string) Is price fair?
        - recommendations: (array) How to improve listing
        - market_insight: (string) Market conditions
        """
        
        return self._call_deepseek(prompt)
    
    def analyze_job(self, job_obj):
        """Analyze job listing with AI"""
        job_data = {
            "title": job_obj.title,
            "company": job_obj.company_name,
            "location": job_obj.location,
            "industry": job_obj.industry,
            "job_category": job_obj.job_category,
            "contract_type": job_obj.contract_type,
            "salary_range": job_obj.salary_range,
            "description": job_obj.job_description[:500] if job_obj.job_description else "",
        }
        
        applications = job_obj.applications.all()
        job_data["total_applications"] = applications.count()
        
        prompt = f"""
        Analyze this job listing:
        {json.dumps(job_data, indent=2)}
        
        Return JSON with:
        - summary: (string) Brief job summary
        - key_requirements: (array) Main requirements
        - ideal_candidate: (string) Who should apply
        - competitiveness: (string) How competitive is this role
        - market_insight: (string) Job market insight
        - recommendations: (array) How to improve listing
        """
        
        return self._call_deepseek(prompt)
    
    def analyze_maintenance(self, maintenance_obj):
        """Analyze a maintenance request"""
        maintenance_data = {
            "title": maintenance_obj.title,
            "description": maintenance_obj.description[:300] if maintenance_obj.description else "",
            "priority": maintenance_obj.priority,
            "status": maintenance_obj.status,
            "category": maintenance_obj.category.name if maintenance_obj.category else "Uncategorized",
            "property": maintenance_obj.property.title if maintenance_obj.property else "N/A",
        }
        
        prompt = f"""
        Analyze this maintenance request:
        {json.dumps(maintenance_data, indent=2)}
        
        Return JSON with:
        - summary: (string) Brief summary
        - severity: (string) How severe is this issue
        - urgency: (string) How urgent is this
        - estimated_repair_time: (string) Estimated time to fix
        - recommendations: (array) Repair recommendations
        - priority_justification: (string) Why this priority level
        """
        
        return self._call_deepseek(prompt)
    
    def chat_assistant(self, user_query, context=None):
        """General AI chat assistant"""
        system_prompt = """
        You are PropNest AI Assistant - a helpful assistant for property, jobs, and maintenance platform.
        Be helpful, professional, and concise.
        """
        
        if context:
            system_prompt += f"\n\nContext: {json.dumps(context)}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]
        
        return self._call_deepseek_chat(messages)
    
    def _call_deepseek(self, prompt, max_tokens=1500, temperature=0.7):
        """Make API call to DeepSeek"""
        if not self.api_key:
            return {"error": "DeepSeek API key not configured"}
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are a helpful AI assistant. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {"response": content}
            else:
                return {"error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"DeepSeek API error: {str(e)}")
            return {"error": str(e)}
    
    def _call_deepseek_chat(self, messages, max_tokens=800, temperature=0.7):
        """Call DeepSeek API with chat messages"""
        if not self.api_key:
            return {"error": "DeepSeek API key not configured"}
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            response = requests.post(self.api_url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return {"response": result['choices'][0]['message']['content']}
            else:
                return {"error": f"API error: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"DeepSeek chat error: {str(e)}")
            return {"error": str(e)}

# Create instance
ai_service = DeepSeekAIService()