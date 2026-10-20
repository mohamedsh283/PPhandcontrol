"""Shared camera/model configuration, also exercised by the packaged smoke test."""
from pathlib import Path


def recognizer_options(model: Path):
    import mediapipe as mp

    return mp.tasks.vision.GestureRecognizerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        canned_gesture_classifier_options=(
            mp.tasks.components.processors.ClassifierOptions(score_threshold=0.5)
        ),
    )
