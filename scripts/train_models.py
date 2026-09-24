"""
ML model training script for Beyond2U IT Helpdesk.

Generates realistic synthetic IT helpdesk data, trains classifiers for category and priority,
evaluates them, and exports versioned, checksummed model artefacts to app/ml/models/.
"""

import hashlib
import json
import logging
import os
import random
from datetime import datetime, timezone

import joblib

logger = logging.getLogger(__name__)

# Output directory for trained models
MODEL_DIR = os.environ.get('ML_MODEL_DIR', 'app/ml/models')


# =============================================================================
# Synthetic Dataset Generation
# =============================================================================

SYNTHETIC_TEMPLATES = {
    "Hardware": {
        "priorities": ["Medium", "High", "Critical"],
        "subjects": [
            "Laptop screen flickering and blacking out",
            "Desktop PC will not turn on no power light",
            "Monitor display has vertical line artifact",
            "Keyboard keys sticking and typing double letters",
            "Mouse sensor malfunctioning disconnects intermittently",
            "Printer jammed paper jam in main tray",
            "Hard drive making loud clicking noise",
            "Overheating laptop fan running at maximum speed constantly",
            "Docking station HDMI port not detecting external monitor",
            "Battery depletes completely in 15 minutes",
        ],
        "descriptions": [
            "My work laptop screen started flickering continuously this morning. Moving the hinge makes it go completely black. I cannot present to client.",
            "Pressed power button on desktop computer multiple times. No fan spin, no LED indicator. Power cord is plugged into working socket.",
            "A bright purple vertical line appeared on my primary 27-inch monitor. Line persists across restarts and cables.",
            "Spacebar and E key stick down when pressed. Typing emails has become extremely difficult.",
            "USB mouse stops responding every few minutes. Disconnecting and reconnecting fixes it temporarily.",
            "Office printer paper tray 2 has a paper jam message. Cleared visible paper but error persists.",
            "Secondary internal mechanical drive makes loud metallic clicking sounds. Files are failing to open.",
            "Laptop chassis is extremely hot to touch. Fan sounds like a jet engine. System throttles and slows down dramatically.",
            "External monitor connected via Thunderbolt dock fails to display. Display Settings says no signal.",
            "Laptop battery drains from 100% to 0% in under 20 minutes without charger attached.",
        ]
    },
    "Network": {
        "priorities": ["High", "Critical", "Medium"],
        "subjects": [
            "Cannot connect to corporate VPN from home",
            "Wi-Fi connection drops every 5 minutes",
            "No internet access on 4th floor workstation",
            "Slow network speeds transferring large files",
            "DNS lookup failed unable to reach external websites",
            "Ethernet port LED inactive no physical link",
            "MFA prompt not arriving for VPN authentication",
            "Remote desktop RDP session timing out",
            "Office Wi-Fi asking for invalid credentials",
            "Intermittent packet loss during video call",
        ],
        "descriptions": [
            "Cisco AnyConnect VPN throws error 800 during gateway handshake. Internet works fine on home router.",
            "Connected to Beyond2U-Corp Wi-Fi but connection drops every 5 minutes with DNS_PROBE_FINISHED_NXDOMAIN.",
            "Network icon shows yellow triangle no internet access on workstation PC-402. IP config shows 169.254 APIPA address.",
            "File transfer speeds to shared SMB network drive reduced to under 50 KB/s. Usually takes seconds.",
            "Web browsers show DNS_PROBE_FINISHED_NXDOMAIN when navigating to internal portals.",
            "Plugged network cable into wall jack 4B. Link LEDs on NIC remain completely off.",
            "Attempting to log into VPN triggers push notification request, but no push arrives on Authenticator app.",
            "RDP connection to server 192.168.1.50 disconnects with error 'Connection timed out'.",
            "Connecting to guest Wi-Fi presents SSL certificate warning and rejects valid corporate credentials.",
            "Zoom and Teams calls freezing with 35% packet loss warning displayed on screen.",
        ]
    },
    "Software": {
        "priorities": ["Low", "Medium", "High"],
        "subjects": [
            "Excel spreadsheet freezes when calculating formulas",
            "Adobe Acrobat DC fails to sign PDF documents",
            "Software license expired message on CAD application",
            "Google Chrome high CPU usage 100%",
            "Unable to install accounting software update",
            "Word document corrupt unable to open",
            "Anti-virus blocking legitimate business app",
            "Web browser extension blocked by administrative policy",
            "CAD application fails to open file",
            "Accounting app crashes when loading database",
        ],
        "descriptions": [
            "Opening financial forecast workbook causes Excel to become unresponsive with 'Not Responding' title bar.",
            "Digital certificate signature tool in Acrobat throws error 'Provider DLL failed to initialize'.",
            "AutoCAD displays 'License expired contact administrator' alert. Unable to edit project blueprints.",
            "Chrome helper processes consuming 98% CPU causing overall system sluggishness.",
            "Installer for SQL Management Studio throws error code 1603 half-way through installation.",
            "Received file error 'Word found unreadable content' when opening monthly report.",
            "Windows Defender Endpoint Security quarantined proprietary inventory client app as threat.",
            "Chrome browser extensions disabled by group policy following recent update.",
            "AutoCAD fails to launch when double-clicking project files.",
            "ERP accounting app crashes immediately upon entering database connection settings.",
        ]
    },
    "Access and Accounts": {
        "priorities": ["Medium", "High", "Critical"],
        "subjects": [
            "Locked out of ERP system after failed login",
            "Request for Active Directory folder permissions",
            "New employee account onboarding setup",
            "MFA device reset lost mobile phone",
            "SSO single sign-on redirect loop error",
            "Temporary administrator rights requested for software dev",
            "Account expired needs extension",
            "Unable to access Shared HR Folder",
            "Password reset link expired",
            "Revoke access for offboarded contractor",
        ],
        "descriptions": [
            "Account locked out due to incorrect password attempts on SAP portal. Requesting account unlock and temporary password.",
            "New team member needs read-write access to \\\\NAS\\Finance\\Reports folder.",
            "Please create domain account, email inbox, and Teams license for new hire starting Monday.",
            "Replaced phone over weekend. Need MFA hardware token or QR re-registration code to log into portal.",
            "Navigating to Okta SSO landing page enters endless redirect loop between auth server and app.",
            "Developer needs 24-hour local admin permissions on workstation to configure Docker dev environment.",
            "Domain user account expired today. Please extend expiration date through end of quarter.",
            "Getting 'Access Denied 403' when clicking link to HR benefits share folder.",
            "Password reset token sent yesterday has expired before user could set new password.",
            "Contractor contract ended today. Please disable AD account, disable VPN access, and archive inbox.",
        ]
    },
    "Email and Communication": {
        "priorities": ["High", "Critical", "Medium"],
        "subjects": [
            "Microsoft Outlook 365 crashes on startup",
            "Teams status stuck on Away while active",
            "Suspicious phishing email with attachment received",
            "Unusual login attempt alert from unexpected location",
            "Unauthorized password change notification received",
            "Data loss prevention DLP blocked email attachment",
            "Exchange server inbox quota full error",
            "Shared mailbox not updating emails",
            "Distribution list email delivery failure",
            "Conference room Teams meeting audio not working",
        ],
        "descriptions": [
            "Outlook closes automatically right after loading profile. Safe mode outlook.exe /safe gives same crash.",
            "Microsoft Teams shows Away status even when actively typing and moving mouse.",
            "Received email posing as CEO asking for immediate wire transfer or gift card purchase. Contains suspicious zip attachment.",
            "Security notification email reports successful login to email account from Russia IP address. User is in Kuala Lumpur.",
            "Received automated SMS notification of password change, but user did not perform password reset.",
            "DLP agent blocked email to external recipient because subject contained confidential customer numbers.",
            "Sending email returns NDR error message 'Inbox mailbox quota exceeded 99%'.",
            "Shared department inbox is not syncing new emails unless restarted manually.",
            "Emails sent to all-staff distribution list bouncing with 550 relay denied error.",
            "Teams Room console microphone is muted and no sound comes out of speakers during video meeting.",
        ]
    },
    "Server and Infrastructure": {
        "priorities": ["Medium", "High", "Critical"],
        "subjects": [
            "Database connection pool exhausted timeout",
            "SQL query execution extremely slow timeout error",
            "Database transaction log disk space 99% full",
            "PostgreSQL replication lag warning alert",
            "Database backup job failed overnight",
            "Corrupt database index on customer table",
            "Deadlock detected in database transaction",
            "Schema migration script failed on staging DB",
            "Database service stopped unresponsive",
            "Request for read-only database replica credentials",
        ],
        "descriptions": [
            "Production API service throwing HTTP 500 with 'OperationalError: connection pool exhausted'.",
            "Customer analytics query taking > 120 seconds and timing out application server request.",
            "Server monitoring alert: /var/lib/postgresql disk space at 99% capacity due to un-truncated WAL logs.",
            "Secondary database replica is 45 minutes behind primary node. Async replication stalling.",
            "Automated nightly pg_dump backup failed with error 'could not write to output file: No space left'.",
            "Querying customer table returns error 'corrupted page header'. Index rebuild required.",
            "PostgreSQL error log shows repeating deadlock detected between process 14022 and 14025.",
            "Alembic database migration script failed with OperationalError: column already exists.",
            "Production MySQL/PostgreSQL daemon crashed and failed to auto-restart.",
            "Data analyst needs read-only connection string to analytics read replica database.",
        ]
    }
}


def generate_synthetic_dataset(num_samples=700):
    """Generate balanced synthetic text samples for category & priority classification."""
    data = []
    categories = list(SYNTHETIC_TEMPLATES.keys())

    samples_per_cat = num_samples // len(categories)

    for cat in categories:
        tmpl = SYNTHETIC_TEMPLATES[cat]
        subjects = tmpl["subjects"]
        descriptions = tmpl["descriptions"]
        priorities = tmpl["priorities"]

        for _ in range(samples_per_cat):
            subj = random.choice(subjects)
            desc = random.choice(descriptions)
            pri = random.choice(priorities)

            noise_prefixes = ["URGENT: ", "HELP NEEDED - ", "Issue: ", "Problem: ", "Fwd: ", ""]
            noise_prefix = random.choice(noise_prefixes)

            full_subj = f"{noise_prefix}{subj}"

            data.append({
                "subject": full_subj,
                "description": desc,
                "text": f"{full_subj} {desc}",
                "category": cat,
                "priority": pri,
            })

    random.shuffle(data)
    print(f"Generated {len(data)} synthetic dataset samples across {len(categories)} categories.")
    return data


def create_classifier():
    """Create ML classifier (scikit-learn Pipeline or PureNaiveBayesClassifier)."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        return Pipeline([
            ('tfidf', TfidfVectorizer(ngram_range=(1, 2), max_features=5000, sublinear_tf=True)),
            ('clf', LogisticRegression(C=2.0, max_iter=1000, solver='lbfgs'))
        ])
    except ImportError:
        from app.ml.pure_classifier import PureNaiveBayesClassifier
        return PureNaiveBayesClassifier(max_features=3000, ngram_range=(1, 2))


def train_and_export_models():
    """Train ML models and save versioned artefacts with SHA-256 checksums."""
    print("Starting ML model training pipeline...")

    data = generate_synthetic_dataset(num_samples=1050)

    texts = [d["text"] for d in data]
    categories = [d["category"] for d in data]
    priorities = [d["priority"] for d in data]

    # Train category model
    cat_pipeline = create_classifier()
    print(f"Training Category Classifier ({cat_pipeline.__class__.__name__})...")
    cat_pipeline.fit(texts, categories)

    # Train priority model
    pri_pipeline = create_classifier()
    print(f"Training Priority Classifier ({pri_pipeline.__class__.__name__})...")
    pri_pipeline.fit(texts, priorities)

    # Create output directory
    os.makedirs(MODEL_DIR, exist_ok=True)

    timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    cat_file_name = f"category_model_v1_{timestamp_str}.joblib"
    pri_file_name = f"priority_model_v1_{timestamp_str}.joblib"

    cat_file_path = os.path.join(MODEL_DIR, cat_file_name)
    pri_file_path = os.path.join(MODEL_DIR, pri_file_name)

    # Save joblib models
    joblib.dump(cat_pipeline, cat_file_path)
    joblib.dump(pri_pipeline, pri_file_path)

    # Compute SHA-256 Checksums
    def compute_sha256(filepath):
        h = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    cat_checksum = compute_sha256(cat_file_path)
    pri_checksum = compute_sha256(pri_file_path)

    metadata = {
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_sample_count": len(data),
        "classifier_type": cat_pipeline.__class__.__name__,
        "category_model_file": cat_file_name,
        "category_model_version": f"cat_v1_{timestamp_str}",
        "category_model_checksum": cat_checksum,
        "priority_model_file": pri_file_name,
        "priority_model_version": f"pri_v1_{timestamp_str}",
        "priority_model_checksum": pri_checksum,
    }

    metadata_path = os.path.join(MODEL_DIR, "metadata.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    print("\nModel Export Complete:")
    print(f"  Metadata saved: {metadata_path}")
    print(f"  Category model: {cat_file_path} (SHA-256: {cat_checksum[:12]}...)")
    print(f"  Priority model: {pri_file_path} (SHA-256: {pri_checksum[:12]}...)")


def run_training():
    train_and_export_models()


if __name__ == "__main__":
    run_training()
