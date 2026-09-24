"""
AI Assistant Service — Intelligent Automation for IT Helpdesk.

Provides:
1. Sentiment & Frustration / Urgency Analyzer (NLP emotional tone & urgency detection)
2. Similar Ticket Finder (Case-Based Reasoning via TF-IDF & Cosine Similarity)
3. Smart Canned Responses & Diagnostic Checklists (Category-aware one-click resolution templates)
"""

import re
import math
import json
import logging
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional

from app.extensions import db
from app.models.ticket import Ticket, TicketStatus, TicketCategory
from app.models.classification import ClassificationPrediction

logger = logging.getLogger(__name__)


# =====================================================================
# 1. Sentiment & Frustration / Urgency Analyzer
# =====================================================================

class SentimentUrgencyAnalyzer:
    """
    Rule-enhanced NLP analyzer tailored for IT Helpdesk communications.
    Evaluates emotional frustration, work-blockage urgency, and polarity.
    """

    # High-impact frustration & work disruption markers (weight 3-5)
    CRITICAL_URGENCY_WORDS = {
        'urgent': 4, 'urgently': 4, 'asap': 4, 'immediately': 4,
        'blocked': 5, 'blocking': 5, 'critical': 4, 'emergency': 5,
        'disaster': 5, 'deadline': 4, 'production': 3, 'down': 4,
        'cannot work': 5, "can't work": 5, 'unable to work': 5,
        'stopped': 4, 'broken': 3, 'fail': 3, 'failed': 3, 'failing': 3,
        'error 412': 4, 'timeout': 3, 'lockout': 4, 'locked out': 4,
        'severe': 4, 'outage': 4, 'escalate': 4, 'crisis': 5,
    }

    # Emotional frustration & dissatisfaction markers (weight 2-4)
    FRUSTRATION_WORDS = {
        'frustrated': 4, 'frustrating': 4, 'terrible': 3, 'horrible': 3,
        'ridiculous': 4, 'unacceptable': 4, 'again': 2, 'repeatedly': 3,
        'still not working': 4, 'tried everything': 4, 'hours': 3,
        'stuck': 3, 'annoying': 3, 'waste of time': 4, 'useless': 3,
        'disappointed': 3, 'unresolved': 3, 'slow': 2, 'nothing works': 4,
    }

    # Courteous / positive sentiment markers (weight -2 to -4)
    COURTESY_WORDS = {
        'please': 2, 'thank': 3, 'thanks': 3, 'thank you': 4,
        'appreciate': 3, 'appreciated': 3, 'kindly': 2, 'hello': 1,
        'good morning': 1, 'good afternoon': 1, 'grateful': 3,
        'whenever possible': 2, 'no rush': 3, 'convenience': 2,
    }

    @classmethod
    def analyze(cls, text: str) -> Dict[str, Any]:
        """
        Analyze input text (subject + description) for emotional tone and urgency.
        Returns detailed scoring, emotion label, detected triggers, and recommendation.
        """
        if not text:
            return {
                'sentiment_label': 'Neutral / Informational',
                'sentiment_score': 0.0,
                'urgency_score': 10,
                'urgency_level': 'Low',
                'tone_badge_class': 'secondary',
                'triggers': [],
                'recommendation': 'Standard queue prioritization.',
            }

        text_lower = text.lower()
        words = re.findall(r'\b[a-z0-9\'-]+\b', text_lower)

        urgency_points = 0
        detected_triggers = []

        # Check multi-word phrases first
        for phrase, weight in cls.CRITICAL_URGENCY_WORDS.items():
            if ' ' in phrase and phrase in text_lower:
                urgency_points += weight * 3
                detected_triggers.append(phrase)

        for phrase, weight in cls.FRUSTRATION_WORDS.items():
            if ' ' in phrase and phrase in text_lower:
                urgency_points += weight * 2
                detected_triggers.append(phrase)

        # Check individual words
        for w in words:
            if w in cls.CRITICAL_URGENCY_WORDS and w not in detected_triggers:
                urgency_points += cls.CRITICAL_URGENCY_WORDS[w] * 2
                detected_triggers.append(w)
            if w in cls.FRUSTRATION_WORDS and w not in detected_triggers:
                urgency_points += cls.FRUSTRATION_WORDS[w] * 2
                detected_triggers.append(w)

        # Courtesy check (reduces frustration score)
        courtesy_points = 0
        for w in words:
            if w in cls.COURTESY_WORDS:
                courtesy_points += cls.COURTESY_WORDS[w]

        # Calculate normalized urgency score (0 to 100)
        raw_score = urgency_points - (courtesy_points * 0.5)
        # Cap and scale to 0-100
        urgency_score = max(5, min(100, int(20 + raw_score * 3.5)))

        # Sentiment score from -1.0 to +1.0
        if urgency_score >= 70:
            sentiment_score = -0.7 - min(0.3, (urgency_score - 70) / 100.0)
            sentiment_label = 'High Frustration / Escalation Risk'
            urgency_level = 'Critical'
            tone_badge_class = 'danger'
            recommendation = 'Client is blocked from working. Immediate response recommended to protect SLA.'
        elif urgency_score >= 45:
            sentiment_score = -0.4 - min(0.2, (urgency_score - 45) / 100.0)
            sentiment_label = 'Urgent / Work Impaired'
            urgency_level = 'High'
            tone_badge_class = 'warning'
            recommendation = 'Issue impairs daily work. Prompt acknowledgement will alleviate user frustration.'
        elif courtesy_points > 3 and urgency_points < 5:
            sentiment_score = 0.5
            sentiment_label = 'Positive / Courteous'
            urgency_level = 'Low'
            tone_badge_class = 'success'
            recommendation = 'Routine polite inquiry. Standard SLA targets apply.'
        else:
            sentiment_score = 0.0
            sentiment_label = 'Neutral / Informational'
            urgency_level = 'Normal'
            tone_badge_class = 'info'
            recommendation = 'Clear diagnostic details provided. Proceed with standard troubleshooting.'

        return {
            'sentiment_label': sentiment_label,
            'sentiment_score': round(sentiment_score, 2),
            'urgency_score': urgency_score,
            'urgency_level': urgency_level,
            'tone_badge_class': tone_badge_class,
            'triggers': detected_triggers[:6],
            'recommendation': recommendation,
        }


# =====================================================================
# 2. Similar Ticket Finder (Case-Based Reasoning via TF-IDF)
# =====================================================================

class SimilarTicketFinder:
    """
    Case-Based Reasoning (CBR) engine.
    Finds past resolved tickets that share technical similarities with the current ticket.
    """

    # Realistic benchmark resolved tickets for instant demonstration and cold-start fallback
    BENCHMARK_RESOLVED_CASES = [
        {
            'ticket_number': 'TKT-20260901-0012',
            'subject': 'Unable to connect to Cisco AnyConnect VPN with Error 412 IPsec timeout',
            'category': 'Network',
            'description': 'Remote client cannot connect to corporate VPN. Error 412: Unable to establish an IPsec tunnel. User restarted router but error continues.',
            'resolution_summary': 'Flushed local DNS cache (ipconfig /flushdns) and restarted Cisco AnyConnect Secure Mobility Agent service in Windows Services. Re-authenticated with MFA push.',
            'resolved_by': 'Muhammad Haziq Rosli',
        },
        {
            'ticket_number': 'TKT-20260903-0045',
            'subject': 'Active Directory account lockout after entering wrong password',
            'category': 'Access & Accounts',
            'description': 'User locked out of corporate workstation and web email after repeated invalid credentials. Needs immediate unlock for client meeting.',
            'resolution_summary': 'Verified employee identity via secondary corporate mobile number. Cleared lockout flag in Active Directory Users & Computers (ADUC) and assisted user with password change.',
            'resolved_by': 'System Administrator',
        },
        {
            'ticket_number': 'TKT-20260905-0018',
            'subject': 'External dual monitors not detected when connected to Thunderbolt docking station',
            'category': 'Hardware',
            'description': 'Dell docking station connected via USB-C does not output video to dual HDMI monitors. Keyboard and mouse work fine.',
            'resolution_summary': 'Executed hard power cycle on dock (unplugged power cable for 30s). Updated Intel Iris Xe graphics driver and reset display topology with Win+Ctrl+Shift+B.',
            'resolved_by': 'Muhammad Haziq Rosli',
        },
        {
            'ticket_number': 'TKT-20260908-0029',
            'subject': 'Microsoft Outlook modern authentication popup loop and disconnected state',
            'category': 'Email & Communication',
            'description': 'Outlook repeatedly prompts for office 365 password every 5 minutes and shows disconnected in the taskbar.',
            'resolution_summary': 'Cleared cached credentials from Windows Credential Manager under Generic Credentials (MicrosoftOffice16_Data). Re-signed in with MFA authenticator.',
            'resolved_by': 'System Administrator',
        },
        {
            'ticket_number': 'TKT-20260910-0033',
            'subject': 'Cannot access staging environment via SSH bastion host key authentication failure',
            'category': 'Server & Infrastructure',
            'description': 'SSH connection to bastion jump server refused with Permission Denied (publickey). ED25519 key was recently rotated.',
            'resolution_summary': 'Fixed SSH private key permissions on client machine (chmod 600 ~/.ssh/id_ed25519) and verified public key fingerprint in staging authorized_keys.',
            'resolved_by': 'Muhammad Haziq Rosli',
        },
    ]

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        """Tokenize and clean text into lowercase words, skipping common stop words."""
        stop_words = {
            'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or',
            'is', 'are', 'was', 'were', 'be', 'been', 'with', 'my', 'i', 'me',
            'have', 'has', 'had', 'do', 'does', 'did', 'this', 'that', 'it', 'we',
        }
        words = re.findall(r'\b[a-z0-9]+\b', text.lower())
        return [w for w in words if len(w) > 2 and w not in stop_words]

    @classmethod
    def _compute_cosine_sim(cls, tokens1: List[str], tokens2: List[str]) -> float:
        """Compute Cosine Similarity between two token lists using TF vectors."""
        if not tokens1 or not tokens2:
            return 0.0

        vec1 = Counter(tokens1)
        vec2 = Counter(tokens2)

        intersection = set(vec1.keys()) & set(vec2.keys())
        dot_product = sum(vec1[x] * vec2[x] for x in intersection)

        mag1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v ** 2 for v in vec2.values()))

        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)

    @classmethod
    def find_similar(cls, ticket: Ticket, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Find top similar resolved or historical tickets using NLP similarity.
        """
        query_text = f"{ticket.subject} {ticket.description or ''}"
        query_tokens = cls._tokenize(query_text)

        candidates = []

        # 1. Search database for resolved/closed tickets (excluding the current ticket itself)
        db_tickets = (
            Ticket.query
            .filter(Ticket.id != ticket.id)
            .filter(Ticket.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED]))
            .filter(Ticket.resolution_summary.isnot(None))
            .limit(20)
            .all()
        )

        for past_ticket in db_tickets:
            past_text = f"{past_ticket.subject} {past_ticket.description or ''} {past_ticket.resolution_summary or ''}"
            past_tokens = cls._tokenize(past_text)
            sim = cls._compute_cosine_sim(query_tokens, past_tokens)

            # Boost similarity if category matches
            if past_ticket.category and ticket.category and past_ticket.category == ticket.category:
                sim = min(1.0, sim + 0.15)

            if sim > 0.10:
                candidates.append({
                    'ticket_number': past_ticket.ticket_number,
                    'subject': past_ticket.subject,
                    'category': past_ticket.category.value if past_ticket.category else 'General',
                    'similarity_pct': int(sim * 100),
                    'status': past_ticket.status.value,
                    'resolution_summary': past_ticket.resolution_summary,
                    'is_live_ticket': True,
                    'resolved_by': past_ticket.assignee.full_name if past_ticket.assignee else 'Assigned Tech',
                })

        # 2. Always augment with benchmark cases if DB has fewer than 2 candidates
        if len(candidates) < limit:
            for bench in cls.BENCHMARK_RESOLVED_CASES:
                # Don't duplicate if ticket number matches
                if any(c['ticket_number'] == bench['ticket_number'] for c in candidates):
                    continue

                bench_text = f"{bench['subject']} {bench['description']} {bench['resolution_summary']}"
                bench_tokens = cls._tokenize(bench_text)
                sim = cls._compute_cosine_sim(query_tokens, bench_tokens)

                # Category boost
                ticket_cat_val = ticket.category.value if ticket.category else ''
                if ticket_cat_val.lower() in bench['category'].lower():
                    sim = min(1.0, sim + 0.20)

                candidates.append({
                    'ticket_number': bench['ticket_number'],
                    'subject': bench['subject'],
                    'category': bench['category'],
                    'similarity_pct': max(42, int(sim * 100)),
                    'status': 'Resolved',
                    'resolution_summary': bench['resolution_summary'],
                    'is_live_ticket': False,
                    'resolved_by': bench['resolved_by'],
                })

        # Sort descending by similarity percentage
        candidates.sort(key=lambda x: x['similarity_pct'], reverse=True)
        return candidates[:limit]


# =====================================================================
# 3. Smart Canned Responses Generator
# =====================================================================

class SmartCannedResponses:
    """
    Intelligent category-driven resolution templates and diagnostics.
    """

    TEMPLATES = {
        'Network': [
            {
                'title': 'Cisco VPN IPsec & DNS Flush',
                'snippet': '1. Flushed DNS cache via ipconfig /flushdns\n2. Power-cycled local router and restarted Cisco AnyConnect adapter.\n3. Verified VPN tunnel established successfully on port 4500.',
            },
            {
                'title': 'Wi-Fi 802.1X Certificate Re-enrollment',
                'snippet': '1. Removed expired corporate Wi-Fi profile.\n2. Re-enrolled device certificate with Beyond2U Internal CA.\n3. Successfully connected to Beyond2U-Corporate SSID.',
            },
        ],
        'Access & Accounts': [
            {
                'title': 'Active Directory Unlock & Password Reset',
                'snippet': '1. Verified user identity via secondary contact info.\n2. Cleared lockout flag in Active Directory domain controller.\n3. Issued temporary password with change-on-next-logon requirement.',
            },
            {
                'title': 'MFA Authenticator Push Re-sync',
                'snippet': '1. Revoked old MFA session tokens in Entra ID / Okta portal.\n2. Guided user through QR code re-enrollment in Microsoft Authenticator app.\n3. Confirmed successful two-factor sign-in.',
            },
        ],
        'Hardware': [
            {
                'title': 'Docking Station Power-Cycle & Topology Reset',
                'snippet': '1. Disconnected all dock cabling and performed 30-second discharge.\n2. Reconnected Thunderbolt cable and refreshed display drivers (Win+Ctrl+Shift+B).\n3. Dual monitors detected and verified running at 60Hz.',
            },
            {
                'title': 'Peripheral / Cable Replacement',
                'snippet': '1. Tested hardware on secondary workstation and confirmed cable degradation.\n2. Replaced faulty video/power cable with verified new inventory.\n3. Device operating within normal operational parameters.',
            },
        ],
        'Software': [
            {
                'title': 'Cache Purge & App Reset',
                'snippet': '1. Cleared application cache and temporary runtime directories (%temp%, AppData/Local).\n2. Restarted application services with elevated permissions.\n3. Functionality restored without data loss.',
            },
            {
                'title': 'O365 / Software License Re-activation',
                'snippet': '1. Cleared stale Office 365 licensing tokens via ospp.vbs.\n2. Re-authenticated corporate user account to pull assigned enterprise license.\n3. Verified application status shows Product Activated.',
            },
        ],
        'Server & Infrastructure': [
            {
                'title': 'SSH Bastion Key Permission & Tunnel Fix',
                'snippet': '1. Audited SSH client key permissions (enforced chmod 600 id_ed25519).\n2. Verified authorized_keys entry on the bastion jump server.\n3. Successfully established tunnel to internal database port.',
            },
        ],
        'Email & Communication': [
            {
                'title': 'Outlook Credential Cleanup',
                'snippet': '1. Removed corrupted credentials from Windows Credential Manager.\n2. Re-authenticated with Exchange Online modern authentication.\n3. Mailbox sync verified with status "Connected to Exchange".',
            },
        ],
    }

    @classmethod
    def get_templates_for_ticket(cls, ticket: Ticket) -> List[Dict[str, str]]:
        """Retrieve relevant canned responses tailored to the ticket's category."""
        category_name = ticket.category.value if ticket.category else 'Network'
        matched = cls.TEMPLATES.get(category_name)
        if not matched:
            # Fallback to network + accounts
            matched = cls.TEMPLATES['Network'] + cls.TEMPLATES['Access & Accounts']
        return matched


# =====================================================================
# 4. Master Orchestrator: AIAssistantService
# =====================================================================

class AIAssistantService:
    """Facade service bringing together Sentiment, CBR, and Smart Templates."""

    @classmethod
    def analyze_ticket(cls, ticket: Ticket) -> Dict[str, Any]:
        """
        Produce a unified AI intelligence payload for a ticket:
        - Sentiment & urgency evaluation
        - Top similar resolved tickets
        - Category-specific canned resolution templates
        """
        full_text = f"{ticket.subject} {ticket.description or ''}"
        sentiment_data = SentimentUrgencyAnalyzer.analyze(full_text)
        similar_tickets = SimilarTicketFinder.find_similar(ticket, limit=3)
        canned_templates = SmartCannedResponses.get_templates_for_ticket(ticket)

        return {
            'sentiment': sentiment_data,
            'similar_tickets': similar_tickets,
            'canned_templates': canned_templates,
        }

    @classmethod
    def analyze_and_record(cls, ticket: Ticket, prediction: Optional[ClassificationPrediction] = None) -> Dict[str, Any]:
        """
        Analyze ticket sentiment and persist it into the ClassificationPrediction model.
        """
        full_text = f"{ticket.subject} {ticket.description or ''}"
        insights = SentimentUrgencyAnalyzer.analyze(full_text)

        if prediction:
            prediction.sentiment_label = insights['sentiment_label']
            prediction.sentiment_score = insights['sentiment_score']
            prediction.urgency_score = insights['urgency_score']
            prediction.urgency_triggers = json.dumps(insights['triggers'])

        return insights
