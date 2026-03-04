import httpx
import asyncio
import random
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_result
from app.core.config import logger
from app.services.ocr_service import solve_captcha_mistral

# Función para decidir si debemos reintentar (Solo si el captcha falló)
def is_captcha_fail(result):
    return isinstance(result, dict) and result.get("error_interno") == "CAPTCHA_FAIL"

class SeniatService:
    def __init__(self):
        self.form_url = "http://contribuyente.seniat.gob.ve/BuscaRif/BuscaRif.jsp"
        self.captcha_url = "http://contribuyente.seniat.gob.ve/BuscaRif/Captcha.jpg"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        
        # RATE LIMIT: Máximo 3 peticiones simultáneas (Semáforo)
        self.semaphore = asyncio.Semaphore(3)

    def _parse_html(self, html: str, rif_buscado: str):
        """Analiza el HTML del SENIAT y extrae la data fiscal."""
        soup = BeautifulSoup(html, "html.parser")
        text_content = soup.get_text().lower()
        
        # 1. Detección de error de captcha
        if "código no coincide" in text_content or ("imagen" in text_content and "coincide" in text_content):
            return {"error_interno": "CAPTCHA_FAIL"}

        # 2. Detección de inexistencia
        if "no existe el contribuyente" in text_content:
            return {"rif_parsed": "NO ENCONTRADO", "nombre": "No existe el contribuyente solicitado"}

        result = {}
        # 3. Extracción de Nombre y RIF (Lógica de tablas)
        center_table = soup.find("table", align="center")
        if center_table:
            font_tag = center_table.find("font", size="2")
            if font_tag:
                full_text = font_tag.get_text(strip=True).replace("\xa0", " ")
                parts = full_text.split(" ", 1)
                result["rif_parsed"] = parts[0] if parts else ""
                result["nombre"] = parts[1] if len(parts) == 2 else ""

        # 4. Extracción de Actividad Económica y Condición
        original_lines = [l.strip() for l in soup.get_text("\n").split('\n') if l.strip()]
        for i, line in enumerate(original_lines):
            if "Actividad Económica:" in line:
                result["actividad_economica"] = line.replace("Actividad Económica:", "").strip()
            if "Condición:" in line:
                result["condicion"] = line.replace("Condición:", "").strip()
            if "Firmas Personales" in line and i + 2 < len(original_lines):
                result["firma_personal"] = original_lines[i+2]

        result["rif_coincide"] = "SI" if result.get("rif_parsed") == rif_buscado else "NO"
        return result

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10), # 2s, 4s, 8s, 16s...
        retry=retry_if_result(is_captcha_fail),
        before_sleep=lambda retry_state: logger.warning(f"⚠️ Captcha incorrecto. Reintento {retry_state.attempt_number} para un RIF.")
    )
    async def consultar_rif(self, rif: str):
        """Ejecuta la consulta completa al SENIAT con control de concurrencia."""
        async with self.semaphore:
            # Delay aleatorio pequeño para humanizar la petición
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            async with httpx.AsyncClient(headers={"User-Agent": self.user_agent}, follow_redirects=True) as client:
                # Paso A: Obtener Sesión y Captcha
                await client.get(self.form_url)
                resp_img = await client.get(self.captcha_url)
                
                # Paso B: Resolver OCR con Mistral
                codigo = await solve_captcha_mistral(client, resp_img.content)
                
                # Paso C: Consultar datos
                payload = {"p_rif": rif, "p_cedula": "", "codigo": codigo, "busca": " Buscar "}
                resp_post = await client.post(self.form_url, data=payload, timeout=25)
                
                # Paso D: Parsear y retornar
                return self._parse_html(resp_post.text, rif)