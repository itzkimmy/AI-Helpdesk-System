"""Knowledge Base service — search, deflection tracking, article management, and feedback."""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import or_, and_, desc

from app.extensions import db
from app.models.knowledge_base import KnowledgeArticle, DeflectionLog, slugify
from app.models.ticket import TicketCategory

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """Service layer for Knowledge Base articles and Ticket Deflection."""

    @staticmethod
    def get_article(article_id: int) -> Optional[KnowledgeArticle]:
        """Fetch article by ID."""
        return db.session.get(KnowledgeArticle, article_id)

    @staticmethod
    def get_by_slug(slug: str) -> Optional[KnowledgeArticle]:
        """Fetch article by unique slug."""
        return KnowledgeArticle.query.filter_by(slug=slug).first()

    @staticmethod
    def list_articles(
        category: Optional[str] = None,
        search_query: Optional[str] = None,
        published_only: bool = True,
        limit: Optional[int] = None,
    ) -> List[KnowledgeArticle]:
        """Query knowledge base articles with optional filters."""
        query = KnowledgeArticle.query

        if published_only:
            query = query.filter_by(is_published=True)

        if category:
            try:
                cat_enum = TicketCategory(category)
                query = query.filter_by(category=cat_enum)
            except ValueError:
                pass

        if search_query and search_query.strip():
            raw_terms = search_query.strip().split()
            terms = [t for t in raw_terms if len(t) >= 2] or raw_terms
            term_filters = []
            for term in terms:
                wildcard = f"%{term}%"
                term_filters.append(
                    or_(
                        KnowledgeArticle.title.ilike(wildcard),
                        KnowledgeArticle.tags.ilike(wildcard),
                        KnowledgeArticle.summary.ilike(wildcard),
                        KnowledgeArticle.content.ilike(wildcard),
                    )
                )
            if term_filters:
                query = query.filter(or_(*term_filters))

        query = query.order_by(
            desc(KnowledgeArticle.helpful_count),
            desc(KnowledgeArticle.view_count),
            desc(KnowledgeArticle.created_at),
        )

        if limit:
            query = query.limit(limit)

        return query.all()

    @staticmethod
    def search_for_deflection(query_text: str, limit: int = 4) -> List[Dict[str, Any]]:
        """
        Instant search optimized for the ticket submission deflection panel.
        Returns serialized lightweight article dicts.
        """
        if not query_text or len(query_text.strip()) < 3:
            return []

        articles = KnowledgeBaseService.list_articles(
            search_query=query_text,
            published_only=True,
            limit=limit,
        )

        results = []
        for a in articles:
            # Highlight snippet or use summary
            snippet = a.summary or (a.content[:140] + '...' if len(a.content) > 140 else a.content)
            results.append({
                'id': a.id,
                'title': a.title,
                'slug': a.slug,
                'category': a.category.value,
                'snippet': snippet,
                'helpful_count': a.helpful_count,
                'views': a.view_count,
            })
        return results

    @staticmethod
    def create_article(
        title: str,
        category: TicketCategory,
        content: str,
        summary: Optional[str] = None,
        tags: Optional[str] = None,
        is_published: bool = True,
        author=None,
    ) -> KnowledgeArticle:
        """Create and persist a new knowledge base article."""
        base_slug = slugify(title)
        if not base_slug:
            base_slug = "kb-article"

        slug = base_slug
        suffix = 1
        while KnowledgeArticle.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{suffix}"
            suffix += 1

        article = KnowledgeArticle(
            title=title.strip(),
            slug=slug,
            category=category,
            content=content.strip(),
            summary=summary.strip() if summary else None,
            tags=tags.strip() if tags else None,
            is_published=is_published,
            author_id=author.id if author else None,
        )
        db.session.add(article)
        db.session.commit()
        logger.info("Knowledge article created: id=%d title=%s", article.id, article.title)
        return article

    @staticmethod
    def update_article(
        article: KnowledgeArticle,
        title: str,
        category: TicketCategory,
        content: str,
        summary: Optional[str] = None,
        tags: Optional[str] = None,
        is_published: bool = True,
    ) -> KnowledgeArticle:
        """Update existing knowledge base article."""
        article.title = title.strip()
        article.category = category
        article.content = content.strip()
        article.summary = summary.strip() if summary else None
        article.tags = tags.strip() if tags else None
        article.is_published = is_published
        article.updated_at = datetime.now(timezone.utc)

        db.session.commit()
        logger.info("Knowledge article updated: id=%d", article.id)
        return article

    @staticmethod
    def delete_article(article: KnowledgeArticle) -> None:
        """Delete article and its deflection logs."""
        article_id = article.id
        db.session.delete(article)
        db.session.commit()
        logger.info("Knowledge article deleted: id=%d", article_id)

    @staticmethod
    def record_view(article_id: int) -> None:
        """Increment article view count atomically."""
        article = db.session.get(KnowledgeArticle, article_id)
        if article:
            article.view_count += 1
            db.session.commit()

    @staticmethod
    def vote_helpful(article_id: int, is_helpful: bool) -> Dict[str, Any]:
        """Record a client thumbs up or thumbs down vote."""
        article = db.session.get(KnowledgeArticle, article_id)
        if not article:
            raise ValueError(f"Article not found: {article_id}")

        if is_helpful:
            article.helpful_count += 1
        else:
            article.not_helpful_count += 1

        db.session.commit()
        return {
            'helpful_count': article.helpful_count,
            'not_helpful_count': article.not_helpful_count,
            'ratio': article.helpful_ratio,
        }

    @staticmethod
    def record_deflection(article_id: int, user_id: Optional[int] = None, search_query: Optional[str] = None) -> DeflectionLog:
        """
        Record when a user solved their issue using an article rather than submitting a ticket.
        Also increments helpful_count.
        """
        article = db.session.get(KnowledgeArticle, article_id)
        if not article:
            raise ValueError(f"Article not found: {article_id}")

        log = DeflectionLog(
            article_id=article.id,
            user_id=user_id,
            search_query=search_query[:255] if search_query else None,
        )
        article.helpful_count += 1
        db.session.add(log)
        db.session.commit()

        logger.info("Ticket deflected by KB article id=%d user_id=%s", article_id, user_id)
        return log

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """Summary metrics for the Admin Dashboard."""
        total_articles = KnowledgeArticle.query.count()
        published_articles = KnowledgeArticle.query.filter_by(is_published=True).count()
        total_views = db.session.query(db.func.sum(KnowledgeArticle.view_count)).scalar() or 0
        total_deflections = DeflectionLog.query.count()
        total_helpful = db.session.query(db.func.sum(KnowledgeArticle.helpful_count)).scalar() or 0

        top_deflected = (
            KnowledgeArticle.query
            .join(DeflectionLog)
            .group_by(KnowledgeArticle.id)
            .order_by(desc(db.func.count(DeflectionLog.id)))
            .limit(5)
            .all()
        )

        return {
            'total_articles': total_articles,
            'published_articles': published_articles,
            'total_views': total_views,
            'total_deflections': total_deflections,
            'total_helpful': total_helpful,
            'top_deflected': top_deflected,
        }
