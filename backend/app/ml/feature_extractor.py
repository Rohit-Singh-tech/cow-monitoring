import numpy as np
import scipy.stats as stats
from typing import List, Union

def extract_67_features(x: Union[List[float], np.ndarray],
                        y: Union[List[float], np.ndarray],
                        z: Union[List[float], np.ndarray]) -> np.ndarray:
    """
    Extracts 67 features matching the new LightGBM training columns.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    
    if len(x) == 0 or len(y) == 0 or len(z) == 0:
        return np.zeros((1, 67), dtype=np.float64)
        
    mag = np.sqrt(x**2 + y**2 + z**2)
    movement = np.abs(np.diff(mag, prepend=mag[0]))
    
    def get_axis_features(arr: np.ndarray, is_mag=False, is_movement=False):
        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr, ddof=0))
        var_val = float(np.var(arr, ddof=0))
        min_val = float(np.min(arr))
        max_val = float(np.max(arr))
        range_val = max_val - min_val
        median_val = float(np.median(arr))
        q25 = float(np.percentile(arr, 25))
        q75 = float(np.percentile(arr, 75))
        abs_mean = float(np.mean(np.abs(arr)))
        energy_val = float(np.sum(arr**2))
        
        if is_movement:
            return [mean_val, std_val, max_val, energy_val]
            
        if is_mag:
            return [mean_val, std_val, var_val, min_val, max_val, range_val, median_val, q25, q75, energy_val]
            
        skew_val = float(stats.skew(arr)) if std_val > 1e-8 else 0.0
        kurt_val = float(stats.kurtosis(arr)) if std_val > 1e-8 else 0.0
        
        diff_arr = np.diff(arr) if len(arr) > 1 else np.array([0.0])
        diff_mean = float(np.mean(diff_arr))
        diff_std = float(np.std(diff_arr))
        diff_max = float(np.max(diff_arr))
        
        return [
            mean_val, std_val, var_val, min_val, max_val, range_val, median_val, 
            q25, q75, abs_mean, energy_val, skew_val, kurt_val, 
            diff_mean, diff_std, diff_max
        ]
        
    feat_x = get_axis_features(x)
    feat_y = get_axis_features(y)
    feat_z = get_axis_features(z)
    feat_mag = get_axis_features(mag, is_mag=True)
    feat_movement = get_axis_features(movement, is_movement=True)
    
    sma = float(np.sum(np.abs(x) + np.abs(y) + np.abs(z)) / len(x))
    
    corr_xy = float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 1e-8 and np.std(y) > 1e-8 else 0.0
    corr_xz = float(np.corrcoef(x, z)[0, 1]) if np.std(x) > 1e-8 and np.std(z) > 1e-8 else 0.0
    corr_yz = float(np.corrcoef(y, z)[0, 1]) if np.std(y) > 1e-8 and np.std(z) > 1e-8 else 0.0
    
    if np.isnan(corr_xy): corr_xy = 0.0
    if np.isnan(corr_xz): corr_xz = 0.0
    if np.isnan(corr_yz): corr_yz = 0.0
    
    # Entropy
    hist, _ = np.histogram(mag, bins=10, density=True)
    hist = hist[hist > 0]
    entropy = float(-np.sum(hist * np.log2(hist))) if len(hist) > 0 else 0.0
    
    all_features = (
        feat_x + feat_y + feat_z + feat_mag + feat_movement + 
        [sma, corr_xy, corr_xz, corr_yz, entropy]
    )
    
    return np.array([all_features], dtype=np.float64)

def extract_78_features(*args, **kwargs):
    pass # Keep for compatibility if needed elsewhere
