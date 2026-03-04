import re
from typing import Optional, Tuple, Dict

class RifMathService:
    # ==========================================
    # CONFIGURACIÓN (Constantes del algoritmo)
    # ==========================================
    ALLOWED_LETTERS = set(["V", "E", "J", "P", "G", "C"])
    UMBRAL_CEDULA_ALTA = 35_000_000 
    LETRA_VALOR = {"V": 1, "E": 2, "J": 3, "P": 4, "G": 5, "C": 6}
    PESOS = [4, 3, 2, 7, 6, 5, 4, 3, 2]

    # ==========================================
    # FUNCIONES LÓGICAS (Cálculo y Extracción)
    # ==========================================
    def calcular_dv(self, letra: str, numero8: str) -> int:
        """Calcula el Dígito Verificador matemático (Módulo 11)."""
        # Limpieza de seguridad: solo dígitos
        numero8_clean = re.sub(r"\D+", "", str(numero8))
        
        # Convertimos letra a su valor numérico + lista de dígitos
        v = [self.LETRA_VALOR.get(letra.upper(), 0)] + [int(x) for x in numero8_clean]
        
        # Multiplicación por pesos y suma
        suma = sum(a * b for a, b in zip(v, self.PESOS))
        
        # Módulo 11
        dv = 11 - (suma % 11)
        if dv in (10, 11): 
            dv = 0
        return dv

    def extraer_partes(self, rif_raw: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """Descompone un RIF en Letra, Cuerpo (8 dígitos) y DV."""
        if not isinstance(rif_raw, str) or not rif_raw.strip():
            return (None, None, None)
            
        t = rif_raw.strip().upper()
        
        # Caso 1: Formato con guiones o espacios (V-12345678-9)
        m = re.match(r"^([VEJPGC])\s*[- ]?\s*([0-9\.]+)(?:\s*[- ]?\s*(\d))?$", t)
        if m:
            letra, num_raw, dv_in = m.groups()
            num_raw = re.sub(r"\D+", "", num_raw)
            # Si el usuario mandó 9 dígitos pegados en num_raw y no hay dv_in
            if dv_in is None and len(num_raw) == 9: 
                return (letra, num_raw[:8], int(num_raw[-1]))
            
            dv_final = int(dv_in) if (dv_in is not None and str(dv_in).isdigit()) else None
            return (letra, num_raw, dv_final)
        
        # Caso 2: Formato pegado (V123456789)
        m2 = re.match(r"^([VEJPGC])(\d+)$", t)
        if m2:
            letra, digits = m2.groups()
            if len(digits) == 9: 
                return (letra, digits[:8], int(digits[-1]))
            return (letra, digits, None)
            
        return (None, None, None)

    # ==========================================
    # AUDITORÍA (Generación de Errores)
    # ==========================================
    def auditar_rif(self, letra: Optional[str], num_raw: Optional[str], dv_in: Optional[int]) -> Dict:
        """Analiza errores estructurales en las partes de un RIF."""
        issues = []
        detalles = []

        if not letra or letra not in self.ALLOWED_LETTERS:
            return {"tipo": "prefijo_invalido", "detalle": "debe iniciar con V/E/J/P/G/C"}

        # Validación de cédula alta (Solo para venezolanos naturales)
        if letra == "V" and num_raw and num_raw.isdigit():
            try:
                if int(num_raw[:8]) > self.UMBRAL_CEDULA_ALTA:
                    issues.append("cedula_alta")
                    detalles.append(f"Cédula > {self.UMBRAL_CEDULA_ALTA}")
            except ValueError:
                pass

        # Validación de longitud
        cuerpo = num_raw or ""
        longitud = len(cuerpo)
        
        if longitud < 8:
            issues.append("longitud_corta")
            detalles.append("Faltan dígitos (no se rellenará)")
        elif longitud > 8:
            issues.append("longitud_larga")
            detalles.append("> 8 dígitos")
        else:
            # Si tiene exactamente 8 dígitos, evaluamos el Dígito Verificador
            # Usamos str() para asegurar que no pase None a calcular_dv
            dv_calculado = self.calcular_dv(str(letra), str(cuerpo))
            if dv_in is not None and dv_in != dv_calculado:
                issues.append("rif_invalido")
                detalles.append("Dígito Verificador incorrecto")

        return {
            "tipo": "; ".join(issues) if issues else "",
            "detalle": " | ".join(detalles) if detalles else ""
        }

    # ORQUESTADOR (Proceso para el API)
   
    def procesar_item_completo(self, rif_original: str, global_id: Optional[str]) -> Dict:
        """
        Realiza el ciclo completo: Audita original -> Intenta corregir -> Audita resultado.
        Devuelve el diccionario con las columnas requeridas por el usuario.
        """
        # 1. Auditoría del original (ANTES)
        letra, num, dv = self.extraer_partes(rif_original)
        audit_antes = self.auditar_rif(letra, num, dv)
        
        # 2. Intentar Corregir/Normalizar
        # Solo se corrige si tiene exactamente la letra permitida y 8 dígitos
        rif_corregido = ""
        if letra and num and len(num) == 8:
            dv_real = self.calcular_dv(letra, num)
            rif_corregido = f"{letra}-{num}-{dv_real}"
        
        # 3. Auditoría de la corrección (DESPUÉS)
        if rif_corregido:
            l_c, n_c, d_c = self.extraer_partes(rif_corregido)
            audit_despues = self.auditar_rif(l_c, n_c, d_c)
        else:
            # Si no se pudo corregir, el error del "después" es el mismo del "antes"
            audit_despues = audit_antes
            
        return {
            "RIF": rif_original,
            "CODIGO IDENTIFICADOR": global_id or "",
            "RIF_CORREGIDO": rif_corregido,
            "TIPO_DE_ERROR_ANTES": audit_antes["tipo"],
            "DETALLES_DEL_ERROR_ANTES": audit_antes["detalle"],
            "TIPO_DE_ERROR_DESPUES": audit_despues["tipo"],
            "DETALLES_DEL_ERROR_DESPUES": audit_despues["detalle"]
        }