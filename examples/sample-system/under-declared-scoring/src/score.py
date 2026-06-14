import pickle
from pathlib import Path


def load_classifier():
    return pickle.loads(Path("models/classifier.pkl").read_bytes())


def rank_applicants(features: dict) -> float:
    clf = load_classifier()
    return float(clf.predict([list(features.values())])[0])
