"""
Pure-Python TF-IDF Naive Bayes Classifier.

Provides deterministic, lightweight ML classification without requiring C-compiled
binary dependencies. Used by default or as a fallback when scikit-learn is unavailable.
"""

import math
import re
from collections import defaultdict


class PureNaiveBayesClassifier:
    """Multinomial Naive Bayes classifier with TF-IDF feature extraction."""

    def __init__(self, max_features=3000, ngram_range=(1, 2)):
        self.max_features = max_features
        self.ngram_range = ngram_range
        self.classes_ = []
        self.vocab_ = {}
        self.idf_ = {}
        self.feature_log_prob_ = {}
        self.class_log_prior_ = {}

    def _tokenize(self, text):
        """Tokenize text into unigrams and bigrams."""
        tokens = re.findall(r'\b\w+\b', text.lower())
        results = []

        if 1 in self.ngram_range:
            results.extend(tokens)

        if 2 in self.ngram_range and len(tokens) > 1:
            bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
            results.extend(bigrams)

        return results

    def fit(self, X, y):
        """Fit the model on text samples X and labels y."""
        self.classes_ = sorted(list(set(y)))
        n_samples = len(X)

        # 1. Document Frequency calculation
        df = defaultdict(int)
        doc_tokens = []
        for text in X:
            tokens = set(self._tokenize(text))
            doc_tokens.append(tokens)
            for token in tokens:
                df[token] += 1

        # Select top max_features by document frequency
        sorted_features = sorted(df.keys(), key=lambda k: df[k], reverse=True)[:self.max_features]
        self.vocab_ = {feat: idx for idx, feat in enumerate(sorted_features)}

        # 2. IDF calculation with smooth_idf=True
        self.idf_ = {}
        for feat in self.vocab_:
            self.idf_[feat] = math.log((1 + n_samples) / (1 + df[feat])) + 1.0

        # 3. Class priors and term probabilities
        class_doc_counts = defaultdict(int)
        class_term_weights = {c: defaultdict(float) for c in self.classes_}

        for text, label in zip(X, y):
            class_doc_counts[label] += 1
            tokens = self._tokenize(text)
            # Term Frequency
            tf = defaultdict(int)
            for t in tokens:
                if t in self.vocab_:
                    tf[t] += 1

            for term, count in tf.items():
                tfidf = (1 + math.log(count)) * self.idf_[term]
                class_term_weights[label][term] += tfidf

        # Compute log priors
        self.class_log_prior_ = {
            c: math.log(class_doc_counts[c] / n_samples) for c in self.classes_
        }

        # Compute log probabilities with Laplace smoothing
        self.feature_log_prob_ = {}
        for c in self.classes_:
            total_weight = sum(class_term_weights[c].values()) + len(self.vocab_)
            self.feature_log_prob_[c] = {}
            for feat in self.vocab_:
                count = class_term_weights[c].get(feat, 0.0) + 1.0
                self.feature_log_prob_[c][feat] = math.log(count / total_weight)

        return self

    def predict_proba(self, X):
        """Predict class probability distribution for text samples X."""
        results = []
        for text in X:
            tokens = self._tokenize(text)
            tf = defaultdict(int)
            for t in tokens:
                if t in self.vocab_:
                    tf[t] += 1

            log_probs = {}
            for c in self.classes_:
                log_prob = self.class_log_prior_[c]
                for term, count in tf.items():
                    tfidf = (1 + math.log(count)) * self.idf_[term]
                    log_prob += count * self.feature_log_prob_[c][term]
                log_probs[c] = log_prob

            # Softmax log probabilities into probabilities
            max_log_prob = max(log_probs.values())
            exp_probs = {c: math.exp(lp - max_log_prob) for c, lp in log_probs.items()}
            total_exp = sum(exp_probs.values())
            probs = [exp_probs[c] / total_exp for c in self.classes_]
            results.append(probs)

        return results

    def predict(self, X):
        """Predict target class for text samples X."""
        probas = self.predict_proba(X)
        return [self.classes_[max(range(len(p)), key=lambda i: p[i])] for p in probas]
