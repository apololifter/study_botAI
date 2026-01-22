import os
from notion_client import Client
from src.utils import logger, retry_on_failure

class NotionAdapter:
    def __init__(self):
        self.token = os.getenv("NOTION_TOKEN")
        if not self.token:
            raise ValueError("NOTION_TOKEN not found in environment variables")
        self.client = Client(auth=self.token)

    @retry_on_failure(max_attempts=3, delay=1.0)
    def fetch_all_pages(self):
        """Search for all pages the integration has access to."""
        results = []
        has_more = True
        start_cursor = None

        while has_more:
            try:
                response = self.client.search(
                    filter={"value": "page", "property": "object"},
                    start_cursor=start_cursor
                )
                results.extend(response.get("results", []))
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
            except Exception as e:
                logger.error(f"Error obteniendo páginas de Notion: {e}")
                if not results:  # Si no hay resultados aún, re-lanzar error
                    raise
                break  # Si ya tenemos algunos resultados, continuar con lo que tenemos
        
        return results

    @retry_on_failure(max_attempts=3, delay=1.0)
    def get_page_content(self, page_id, depth=0, max_depth=5):
        """
        Retrieve text from a page. Recurses into child_pages up to max_depth.
        """
        if depth > max_depth:
            return ""

        content_lines = []
        has_more = True
        start_cursor = None

        while has_more:
            try:
                blocks = self.client.blocks.children.list(
                    block_id=page_id,
                    start_cursor=start_cursor
                )
                
                for block in blocks.get("results", []):
                    # 1. Extract text from standard blocks
                    text = self._extract_text_from_block(block)
                    if text:
                        content_lines.append(text)
                    
                    # 2. Recursion: Check for child pages
                    if block.get("type") == "child_page" and depth < max_depth:
                        child_title = block.get("child_page", {}).get("title", "Sub-page")
                        content_lines.append(f"\n--- Contenido de Sub-página: {child_title} ---")
                        
                        # Recursive call
                        child_content = self.get_page_content(block["id"], depth + 1, max_depth)
                        content_lines.append(child_content)
                        content_lines.append(f"--- Fin Sub-página: {child_title} ---\n")

                has_more = blocks.get("has_more", False)
                start_cursor = blocks.get("next_cursor")
            except Exception as e:
                logger.error(f"Error obteniendo contenido de página {page_id}: {e}")
                if not content_lines and depth == 0:  # Only raise if it's the root page and empty
                    raise
                break 
        
        return "\n".join(content_lines)

    def extract_page_title(self, page):
        """
        Extrae el título de una página de Notion.
        
        Args:
            page: Objeto de página de Notion API
            
        Returns:
            str: Título de la página o "Untitled" si no se encuentra
        """
        title = "Untitled"
        props = page.get("properties", {})
        # Title property name varies, usually "title" or "Name"
        for key, val in props.items():
            if val.get("id") == "title":
                if val.get("title"):
                    title = val["title"][0].get("plain_text", "Untitled")
                break
        return title

    def _extract_text_from_block(self, block):
        """Helper to extract text from various block types."""
        block_type = block.get("type")
        if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item", "to_do", "toggle"]:
            rich_text = block.get(block_type, {}).get("rich_text", [])
            return "".join([t.get("plain_text", "") for t in rich_text])
        return None
