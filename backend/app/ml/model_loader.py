import os
import json
import joblib
import logging
import warnings
import numpy as np
from typing import Dict, Any, List
from app.config import settings
from app.ml.feature_extractor import extract_67_features

# Suppress sklearn UserWarning about feature names
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")

logger = logging.getLogger("cow_logger.ml")

# Human readable activity names mapping
ACTIVITY_DESCRIPTIONS = {
    "ATT": "Attacking / Head Butting",
    "BMN": "Bellowing / Moaning",
    "DEF": "Defecation",
    "DRN": "Drinking Water",
    "ETC": "Other Activity",
    "FED": "Feeding / Trough Intake",
    "FEP": "Feeding (Pasture)",
    "FES": "Feeding (Silage)",
    "GRZ": "Grazing Field",
    "LCK": "Licking / Self-Grooming",
    "MOV": "Walking / Moving",
    "NAN": "Other Activity",
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
            cls._instance.load_attempted = False
            cls._instance.models_dict = {}
            cls._instance.metadata = {}
        return cls._instance

    def load_models(self, path: str = None) -> bool:
        if self.is_loaded:
            return True
        if self.load_attempted:
            return False
            
        self.load_attempted = True
            
        model_path = path or settings.MODEL_PATH
        if not os.path.exists(model_path) or not os.path.isdir(model_path):
            logger.warning(f"ML Model directory not found at {model_path}. Running with fallback heuristic engine.")
            return False

        try:
            logger.info(f"Loading LightGBM ML models from {model_path} into Singleton Manager...")
            
            # Load metadata if exists
            meta_path = os.path.join(model_path, "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    self.metadata = json.load(f)
            
            act_model_path = os.path.join(model_path, "activity_model.pkl")
            if os.path.exists(act_model_path):
                self.models_dict["activity_model"] = joblib.load(act_model_path)
            
            heat_model_path = os.path.join(model_path, "heat_model.pkl")
            if os.path.exists(heat_model_path):
                self.models_dict["heat_model"] = joblib.load(heat_model_path)
                
            act_enc_path = os.path.join(model_path, "activity_encoder.pkl")
            if os.path.exists(act_enc_path):
                self.models_dict["activity_encoder"] = joblib.load(act_enc_path)
                
            anomaly_model_path = os.path.join(model_path, "anomaly_model.pkl")
            if os.path.exists(anomaly_model_path):
                self.models_dict["anomaly_model"] = joblib.load(anomaly_model_path)
            
            # Load baseline and threshold data
            baseline_mean_path = os.path.join(model_path, "baseline_mean.pkl")
            if os.path.exists(baseline_mean_path):
                self.models_dict["baseline_mean"] = joblib.load(baseline_mean_path)

            baseline_std_path = os.path.join(model_path, "baseline_std.pkl")
            if os.path.exists(baseline_std_path):
                self.models_dict["baseline_std"] = joblib.load(baseline_std_path)

            anomaly_threshold_path = os.path.join(model_path, "anomaly_threshold.pkl")
            if os.path.exists(anomaly_threshold_path):
                self.models_dict["anomaly_threshold"] = float(joblib.load(anomaly_threshold_path))

            deviation_threshold_path = os.path.join(model_path, "deviation_threshold.pkl")
            if os.path.exists(deviation_threshold_path):
                self.models_dict["deviation_threshold"] = float(joblib.load(deviation_threshold_path))

            self.is_loaded = True
            logger.info("Successfully loaded ML Activity, Heat, and Anomaly models into RAM.")
            return True
        except Exception as e:
            logger.error(f"Failed to load ML models from {model_path}: {e}")
            return False

    def predict(self, x: List[float], y: List[float], z: List[float]) -> Dict[str, Any]:
        """
        Takes raw XYZ accelerometer series (10 Hz, 80 samples default),
        extracts 67 features, and returns Activity and Heat predictions.
        """
        features = extract_67_features(x, y, z)
        
        if not self.is_loaded:
            self.load_models()

        if self.is_loaded and "activity_model" in self.models_dict:
            try:
                act_model = self.models_dict["activity_model"]
                act_encoder = self.models_dict.get("activity_encoder")
                heat_model = self.models_dict.get("heat_model")
                anomaly_model = self.models_dict.get("anomaly_model")
                baseline_mean = self.models_dict.get("baseline_mean")
                baseline_std = self.models_dict.get("baseline_std")
                anomaly_threshold = self.models_dict.get("anomaly_threshold", -1e-8)
                deviation_threshold = self.models_dict.get("deviation_threshold", 1.5)
                
                # Compute statistical deviation score if baselines are loaded
                deviation_score = 0.0
                is_deviating = False
                if baseline_mean is not None and baseline_std is not None:
                    # Avoid division by zero
                    std_safe = np.where(baseline_std.values == 0, 1e-8, baseline_std.values)
                    scaled_features = (features[0] - baseline_mean.values) / std_safe
                    deviation_score = float(np.mean(np.abs(scaled_features)))
                    is_deviating = bool(deviation_score > deviation_threshold)
                
                # Activity prediction
                act_pred = act_model.predict(features)[0]
                act_probs = act_model.predict_proba(features)[0]
                
                if act_encoder is not None:
                    activity_code = str(act_encoder.inverse_transform([act_pred])[0])
                else:
                    activity_code = str(act_pred)
                    
                # Map ETC/BMW to OTHER_ACTIVITY explicitly
                if activity_code in ["ETC", "BMW"]:
                    activity_code = "OTHER_ACTIVITY"
                    
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
                    
                heat_alert = "HIGH" if heat_prob > 0.7 else ("MODERATE" if heat_prob > 0.4 else "NORMAL")
                    
                # Anomaly prediction
                anomaly_result = {"is_anomaly": False, "score": 0.0}
                if anomaly_model is not None:
                    if hasattr(anomaly_model, "decision_function"):
                        anom_score = float(anomaly_model.decision_function(features)[0])
                        anomaly_result["score"] = anom_score
                        anomaly_result["is_anomaly"] = bool(anom_score < anomaly_threshold)
                    else:
                        anom_pred = anomaly_model.predict(features)[0]
                        anomaly_result["is_anomaly"] = bool(anom_pred == -1)
                        if hasattr(anomaly_model, "score_samples"):
                            anomaly_result["score"] = float(anomaly_model.score_samples(features)[0])
                    
                # Health-risk decision logic
                if anomaly_result["is_anomaly"] or is_deviating or heat_alert == "HIGH":
                    health_risk = "HIGH_RISK"
                elif activity_code == "OTHER_ACTIVITY" or heat_alert == "MODERATE":
                    health_risk = "MONITOR"
                else:
                    health_risk = "HEALTHY"
                    
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
                        "alert_level": heat_alert
                    },
                    "anomaly_detection": anomaly_result,
                    "deviation_metrics": {
                        "score": round(deviation_score, 4),
                        "is_deviating": is_deviating,
                        "threshold": round(deviation_threshold, 4)
                    },
                    "health_risk_decision": health_risk,
                    "features_extracted_count": 67
                }
            except Exception as e:
                logger.error(f"Inference error: {e}")
                
        # Heuristic fallback if models not loaded
        mag = np.sqrt(np.array(x)**2 + np.array(y)**2 + np.array(z)**2)
        std_mag = float(np.std(mag)) if len(mag) > 0 else 0.0
        
        fallback_act = "RUS" if std_mag < 0.5 else ("GRZ" if std_mag < 2.0 else "MOV")
        
        # Heuristic health logic
        heat_alert = "HIGH" if std_mag > 3.5 else "NORMAL"
        health_risk = "HIGH_RISK" if heat_alert == "HIGH" else ("MONITOR" if fallback_act == "MOV" else "HEALTHY")
        
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
                "alert_level": heat_alert
            },
            "anomaly_detection": {"is_anomaly": False, "score": 0.0},
            "deviation_metrics": {"score": 0.0, "is_deviating": False, "threshold": 1.5},
            "health_risk_decision": health_risk,
            "features_extracted_count": 67
        }

def get_ml_manager() -> MLModelManager:
    manager = MLModelManager()
    if not manager.is_loaded:
        manager.load_models()
    return manager
