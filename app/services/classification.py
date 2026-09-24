"""
Classification service — ML model loading, inference, and confidence reporting.

Loads versioned, checksummed model artefacts. Never loads untrusted models.
"""

import hashlib
import json
import logging
import os

import joblib

logger = logging.getLogger(__name__)


class ClassificationService:
    """ML-based ticket classification for category and priority prediction."""

    _category_model = None
    _priority_model = None
    _metadata = None
    _loaded = False

    def __init__(self, model_dir=None):
        self.model_dir = model_dir or os.environ.get('ML_MODEL_DIR', 'app/ml/models')

    def is_ready(self):
        """Check if models are loaded and available."""
        if not ClassificationService._loaded:
            self._try_load()
        return (
            ClassificationService._category_model is not None
            and ClassificationService._priority_model is not None
        )

    def _try_load(self):
        """Attempt to load model artefacts with checksum verification."""
        try:
            metadata_path = os.path.join(self.model_dir, 'metadata.json')
            if not os.path.exists(metadata_path):
                logger.info('Model metadata not found at %s', metadata_path)
                return

            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            # Load category & priority model
            cat_path = os.path.join(self.model_dir, metadata.get('category_model_file', ''))
            pri_path = os.path.join(self.model_dir, metadata.get('priority_model_file', ''))

            if not os.path.exists(cat_path) or not os.path.exists(pri_path):
                logger.info('Model files not found')
                return

            # Verify checksums
            if not self._verify_checksum(cat_path, metadata.get('category_model_checksum')):
                logger.error('Category model checksum mismatch — refusing to load')
                return
            if not self._verify_checksum(pri_path, metadata.get('priority_model_checksum')):
                logger.error('Priority model checksum mismatch — refusing to load')
                return

            ClassificationService._category_model = joblib.load(cat_path)
            ClassificationService._priority_model = joblib.load(pri_path)
            ClassificationService._metadata = metadata
            ClassificationService._loaded = True

            logger.info(
                'Models loaded: category=%s priority=%s',
                metadata.get('category_model_version'),
                metadata.get('priority_model_version'),
            )

        except Exception as e:
            logger.error('Failed to load models: %s', str(e))

    def predict(self, subject, description):
        """
        Predict category and priority for a ticket.
        
        Returns dict with predictions, confidence scores, and model versions.
        """
        if not self.is_ready():
            return {
                'category': None,
                'priority': None,
                'category_confidence': None,
                'priority_confidence': None,
                'category_model_version': None,
                'priority_model_version': None,
            }

        text = f'{subject} {description}'
        metadata = ClassificationService._metadata

        # Category prediction
        cat_model = ClassificationService._category_model
        cat_pred = cat_model.predict([text])[0]
        cat_proba = None
        if hasattr(cat_model, 'predict_proba'):
            probas = cat_model.predict_proba([text])[0]
            cat_proba = float(max(probas))

        # Priority prediction
        pri_model = ClassificationService._priority_model
        pri_pred = pri_model.predict([text])[0]
        pri_proba = None
        if hasattr(pri_model, 'predict_proba'):
            probas = pri_model.predict_proba([text])[0]
            pri_proba = float(max(probas))

        return {
            'category': cat_pred,
            'priority': pri_pred,
            'category_confidence': cat_proba,
            'priority_confidence': pri_proba,
            'category_model_version': metadata.get('category_model_version'),
            'priority_model_version': metadata.get('priority_model_version'),
        }

    @staticmethod
    def _verify_checksum(filepath, expected_checksum):
        """Verify SHA-256 checksum of a model file."""
        if not expected_checksum:
            logger.warning('No checksum provided for %s — refusing to load unverified model', filepath)
            return False

        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        actual = sha256.hexdigest()
        return actual == expected_checksum
