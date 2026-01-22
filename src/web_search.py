import os
import time
from typing import List, Dict, Optional
from ddgs import DDGS

class WebSearch:
    """Busca información complementaria en internet para enriquecer el contexto."""
    
    def __init__(self):
        try:
            self.ddgs = DDGS()
            self.enabled = True
        except Exception as e:
            print(f"Warning: No se pudo inicializar DuckDuckGo Search: {e}")
            print("El bot continuará sin búsqueda web.")
            self.enabled = False
    
    def search_topic(self, topic_title: str, max_results: int = 5, timeout: int = 10) -> List[Dict[str, str]]:
        """
        Busca información sobre el tema en internet.
        
        Args:
            topic_title: Título del tema a buscar
            max_results: Número máximo de resultados a retornar
            timeout: Tiempo máximo en segundos para la búsqueda
            
        Returns:
            Lista de diccionarios con 'title', 'snippet', 'url'
        """
        if not self.enabled:
            return []
        
        try:
            # Búsqueda optimizada: tema + "documentación" o "ejemplos" o "guía"
            query = f"{topic_title} documentación ejemplos guía tutorial"
            
            results = []
            start_time = time.time()
            
            # Intentar búsqueda con timeout implícito
            for r in self.ddgs.text(query, max_results=max_results):
                # Verificar timeout
                if time.time() - start_time > timeout:
                    print(f"Búsqueda web timeout después de {timeout}s. Usando resultados parciales.")
                    break
                
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", "")
                })
            
            return results
        except Exception as e:
            print(f"Error en búsqueda web (continuando sin web): {e}")
            # Deshabilitar búsqueda web para evitar más intentos fallidos
            self.enabled = False
            return []
    
    def format_context(self, search_results: List[Dict[str, str]], max_chars: int = 2000) -> str:
        """
        Formatea los resultados de búsqueda en un texto contextual para el prompt.
        
        Args:
            search_results: Lista de resultados de búsqueda
            max_chars: Máximo de caracteres a incluir
            
        Returns:
            Texto formateado con información de internet
        """
        if not search_results:
            return ""
        
        formatted = "\n\n=== Información complementaria de internet ===\n"
        char_count = len(formatted)
        
        for i, result in enumerate(search_results, 1):
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            url = result.get("url", "")
            
            entry = f"\n[{i}] {title}\n{snippet}\nFuente: {url}\n"
            
            if char_count + len(entry) > max_chars:
                break
            
            formatted += entry
            char_count += len(entry)
        
        formatted += "\n=== Fin información complementaria ===\n"
        return formatted
    
    def get_enriched_context(self, topic_title: str, base_content: str, max_web_chars: int = 2000) -> str:
        """
        Obtiene contexto enriquecido combinando contenido base + búsqueda web.
        Si falla la búsqueda web, retorna solo el contenido base (fallback graceful).
        
        Args:
            topic_title: Título del tema
            base_content: Contenido base de Notion
            max_web_chars: Máximo de caracteres de información web a agregar
            
        Returns:
            Texto combinado con contenido base + información de internet (o solo base si falla)
        """
        if not self.enabled:
            print("Búsqueda web deshabilitada. Usando solo contenido de Notion.")
            return base_content
        
        print(f"Buscando información complementaria sobre '{topic_title}' en internet...")
        
        try:
            search_results = self.search_topic(topic_title, max_results=5, timeout=10)
            
            if not search_results:
                print("No se encontraron resultados de búsqueda web. Usando solo contenido de Notion.")
                return base_content
            
            print(f"Encontrados {len(search_results)} resultados web. Enriqueciendo contexto...")
            web_context = self.format_context(search_results, max_chars=max_web_chars)
            
            # Combinar: contenido base + información web
            enriched = f"{base_content}\n{web_context}"
            
            return enriched
        except Exception as e:
            print(f"Error crítico en búsqueda web (usando fallback): {e}")
            print("Continuando con solo contenido de Notion.")
            # Deshabilitar para evitar más intentos
            self.enabled = False
            return base_content
