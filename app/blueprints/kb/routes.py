"""Knowledge Base routes — article directory, article detail, voting, instant search API, and deflection logging."""

import logging
from flask import render_template, request, jsonify, abort, redirect, url_for, flash
from flask_login import current_user

from app.blueprints.kb import kb_bp
from app.models.ticket import TicketCategory
from app.models.knowledge_base import KnowledgeArticle
from app.services.knowledge_base import KnowledgeBaseService

logger = logging.getLogger(__name__)


@kb_bp.before_request
def restrict_client_access():
    """Knowledge Base is internal for technical staff and administrators."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    if getattr(current_user, 'is_client', False):
        flash('Knowledge Base is reserved for technical staff and administrators.', 'info')
        return redirect(url_for('client.dashboard'))


@kb_bp.route('/')
def index():
    """Knowledge base home page with search and category filters."""
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()

    articles = KnowledgeBaseService.list_articles(
        category=category or None,
        search_query=query or None,
        published_only=True,
    )

    categories = [c.value for c in TicketCategory]
    stats = KnowledgeBaseService.get_stats()

    return render_template(
        'kb/index.html',
        articles=articles,
        query=query,
        selected_category=category,
        categories=categories,
        stats=stats,
    )


@kb_bp.route('/<slug>')
def article_detail(slug):
    """View single article and record view count."""
    article = KnowledgeBaseService.get_by_slug(slug)
    if not article or not article.is_published:
        abort(404)

    # Record view
    KnowledgeBaseService.record_view(article.id)

    # Fetch related articles in same category
    related = (
        KnowledgeArticle.query
        .filter(
            KnowledgeArticle.category == article.category,
            KnowledgeArticle.id != article.id,
            KnowledgeArticle.is_published.is_(True),
        )
        .order_by(KnowledgeArticle.helpful_count.desc())
        .limit(4)
        .all()
    )

    return render_template(
        'kb/article_detail.html',
        article=article,
        related=related,
    )


@kb_bp.route('/<int:article_id>/vote', methods=['POST'])
def vote_article(article_id):
    """AJAX endpoint for helpfulness feedback (thumbs up / thumbs down)."""
    data = request.get_json(silent=True) or request.form
    helpful_val = data.get('helpful')
    is_helpful = str(helpful_val).lower() in ('true', '1', 'yes')

    try:
        result = KnowledgeBaseService.vote_helpful(article_id, is_helpful)
        return jsonify({
            'success': True,
            'helpful_count': result['helpful_count'],
            'not_helpful_count': result['not_helpful_count'],
            'ratio': result['ratio'],
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error("Error recording vote for article %d: %s", article_id, str(e))
        return jsonify({'success': False, 'error': 'Server error'}), 500


@kb_bp.route('/api/search')
def api_search():
    """Instant search endpoint for ticket submission live deflection."""
    q = request.args.get('q', '').strip()
    limit = request.args.get('limit', 4, type=int)

    results = KnowledgeBaseService.search_for_deflection(q, limit=limit)
    return jsonify({
        'query': q,
        'count': len(results),
        'results': results,
    })


@kb_bp.route('/api/deflect', methods=['POST'])
def api_deflect():
    """
    Log when a user cancels their ticket submission because a KB article solved their issue.
    Returns celebratory feedback and deflection confirmation.
    """
    data = request.get_json(silent=True) or request.form
    article_id = data.get('article_id')
    query_text = data.get('query', '')

    if not article_id:
        return jsonify({'success': False, 'error': 'article_id required'}), 400

    try:
        article_id = int(article_id)
        user_id = current_user.id if current_user.is_authenticated else None
        KnowledgeBaseService.record_deflection(
            article_id=article_id,
            user_id=user_id,
            search_query=query_text,
        )
        return jsonify({
            'success': True,
            'message': 'Thank you! Glad this solved your issue without waiting in the IT queue.'
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error("Error recording deflection: %s", str(e))
        return jsonify({'success': False, 'error': 'Server error'}), 500
