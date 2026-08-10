import os
import joblib
import logging
import numpy as np
from typing import Dict, Any, List
from app.config import settings
from app.ml.feature_extractor import extract_78_features

logger = logging.getLogger("cow_logger.ml")

# Human readable activity names mapping
ACTIVITY_DESCRIPTIONS = {
    "ATT": "Attacking / Head Butting",
    "DEF": "Defecation",
    "DRN": "Drinking Water",
    "ETC": "Other Activity",
    "FED": "Feeding / Trough Intake",
    "FEP": "Feeding (Pasture)",
    "FES": "Feeding (Silage)",
    "GRZ": "Grazing Field",
    "LCK": "Licking / Self-Grooming",
    "MOV": "Walking / Moving",
    "REL": "Resting / Lying Flat",
    "RES": "Resting / Lying Down",
    "RUS": "Ruminating (Chewing Cud)",
    "SLT": "Salt Lick Intake",
    "URI": "Urination"
}

class MLModelManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MLModelManager, cls).__new__(cls)
            cls._instance.is_loaded = False
            cls._instance.models_dict = {}
        return cls._instance

    def load_models(self, path: str = None) -> bool:
        if self.is_loaded:
            return True
            
        model_path = path or settings.MODEL_PATH
        if not os.path.exists(model_path):
            logger.warning(f"ML Model file not found at {model_path}. Running with fallback heuristic engine.")
            return False

        try:
            logger.info(f"Loading XGBoost ML models from {model_path} into Singleton Manager...")
            data = joblib.load(model_path)
            if isinstance(data, dict):
                self.models_dict = data
                self.is_loaded = True
                logger.info("Successfully loaded XGBoost Activity and Heat classification models into RAM.")
                return True
            else:
                logger.error(f"Unexpected pickle object format at {model_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to load ML models from {model_path}: {e}")
            return False

    def predict(self, x: List[float], y: List[float], z: List[float]) -> Dict[str, Any]:
        """
        Takes raw XYZ accelerometer series (10 Hz, 80 samples default),
        extracts 78 features, and returns Activity and Heat predictions.
        """
        features = extract_78_features(x, y, z)
        
        if not self.is_loaded:
            self.load_models()

        if self.is_loaded and "activity_model" in self.models_dict:
            try:
                act_model = self.models_dict["activity_model"]
                act_encoder = self.models_dict.get("activity_encoder")
                heat_model = self.models_dict.get("heat_model")
                
                # Activity prediction
                act_pred = act_model.predict(features)[0]
                act_probs = act_model.predict_proba(features)[0]
                
                if act_encoder is not None:
                    activity_code = str(act_encoder.inverse_transform([act_pred])[0])
                else:
                    activity_code = str(act_pred)
                    
                activity_prob = float(np.max(act_probs))
                activity_desc = ACTIVITY_DESCRIPTIONS.get(activity_code, activity_code)
                
                # Heat prediction
                if heat_model is not None:
                    heat_pred = int(heat_model.predict(features)[0])
                    heat_probs = heat_model.predict_proba(features)[0]
                    heat_prob = float(heat_probs[1]) if len(heat_probs) > 1 else float(heat_pred)
                else:
                    heat_pred = 0
                    heat_prob = 0.05
                    
                return {
                    "ml_engine_status": "ACTIVE",
                    "activity": {
                        "code": activity_code,
                        "description": activity_desc,
                        "confidence": round(activity_prob, 4),
                        "is_ruminating": activity_code == "RUS",
                        "is_grazing": activity_code in ["GRZ", "FED", "FEP", "FES"],
                        "is_resting": activity_code in ["RES", "REL"]
                    },
                    "heat_detection": {
                        "in_heat": bool(heat_pred == 1),
                        "heat_probability": round(heat_prob, 4),
                        "alert_level": "HIGH" if heat_prob > 0.7 else ("MODERATE" if heat_prob > 0.4 else "NORMAL")
                    },
                    "features_extracted_count": 78
                }
            except Exception as e:
                logger.error(f"Inference error: {e}")
                
        # Heuristic fallback if models not loaded
        mag = np.sqrt(np.array(x)**2 + np.array(y)**2 + np.array(z)**2)
        std_mag = float(np.std(mag)) if len(mag) > 0 else 0.0
        
        fallback_act = "RUS" if std_mag < 0.5 else ("GRZ" if std_mag < 2.0 else "MOV")
        return {
            "ml_engine_status": "HEURISTIC_FALLBACK",
            "activity": {
                "code": fallback_act,
                "description": ACTIVITY_DESCRIPTIONS.get(fallback_act, fallback_act),
                "confidence": 0.75,
                "is_ruminating": fallback_act == "RUS",
                "is_grazing": fallback_act == "GRZ",
                "is_resting": fallback_act == "RES"
            },
            "heat_detection": {
                "in_heat": std_mag > 3.5,
                "heat_probability": 0.85 if std_mag > 3.5 else 0.10,
                "alert_level": "HIGH" if std_mag > 3.5 else "NORMAL"
            },
            "features_extracted_count": 78
        }

def get_ml_manager() -> MLModelManager:
    manager = MLModelManager()
    if not manager.is_loaded:
        manager.load_models()
    return manager
