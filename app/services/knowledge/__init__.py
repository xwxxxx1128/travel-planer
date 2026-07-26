from app.services.knowledge.crawler_service import IncrementalCrawlerService, CrawlRequest
from app.services.knowledge.vector_store import ChromaStore

crawler_service = IncrementalCrawlerService()
vector_store = ChromaStore()
