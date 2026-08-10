import numpy as np
import scipy.stats as stats
from typing import List, Union

def extract_78_features(x: Union[List[float], np.ndarray],
                        y: Union[List[float], np.ndarray],
                        z: Union[List[float], np.ndarray],
                        fs: float = 10.0) -> np.ndarray:
    """
    Extracts 78 statistical, frequency, correlation, and jerk features from XYZ accelerometer signals.
    Optimized with pure Numpy/Scipy for ultra-low memory footprint (Render 512 MB RAM).
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    
    # Ensure min window length (e.g. pad or truncate if needed, default expected 80 samples)
    if len(x) == 0 or len(y) == 0 or len(z) == 0:
        return np.zeros((1, 78), dtype=np.float64)
        
    mag = np.sqrt(x**2 + y**2 + z**2)
    
    def get_axis_features(arr: np.ndarray) -> List[float]:
        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr, ddof=0))
        min_val = float(np.min(arr))
        max_val = float(np.max(arr))
        range_val = max_val - min_val
        median_val = float(np.median(arr))
        var_val = float(np.var(arr, ddof=0))
        rms_val = float(np.sqrt(np.mean(arr**2)))
        energy_val = float(np.sum(arr**2))
        
        skew_val = float(stats.skew(arr)) if std_val > 1e-8 else 0.0
        kurt_val = float(stats.kurtosis(arr)) if std_val > 1e-8 else 0.0
        
        q75, q25 = np.percentile(arr, [75, 25])
        iqr_val = float(q75 - q25)
        
        # Zero crossings relative to mean
        zero_cross = int(np.where(np.diff(np.signbit(arr - mean_val)))[0].size)
        
        # FFT Spectral features
        fft_vals = np.abs(np.fft.rfft(arr - mean_val))
        freqs = np.fft.rfftfreq(len(arr), d=1.0 / fs)
        
        if len(fft_vals) > 1 and np.sum(fft_vals[1:]) > 1e-8:
            dom_freq = float(freqs[1 + np.argmax(fft_vals[1:])])
            spec_energy = float(np.sum(fft_vals[1:]**2))
            psd = fft_vals[1:] / np.sum(fft_vals[1:])
            spec_entropy = float(-np.sum(psd * np.log2(psd + 1e-12)))
            spec_centroid = float(np.sum(freqs[1:] * fft_vals[1:]) / np.sum(fft_vals[1:]))
        else:
            dom_freq, spec_energy, spec_entropy, spec_centroid = 0.0, 0.0, 0.0, 0.0
            
        return [
            mean_val, std_val, min_val, max_val, range_val, median_val, var_val,
            rms_val, energy_val, skew_val, kurt_val, iqr_val, zero_cross,
            dom_freq, spec_energy, spec_entropy, spec_centroid
        ]
        
    feat_x = get_axis_features(x)
    feat_y = get_axis_features(y)
    feat_z = get_axis_features(z)
    feat_mag = get_axis_features(mag)
    
    # Signal Vector Magnitude Area (SMA)
    sma = float(np.sum(np.abs(x) + np.abs(y) + np.abs(z)) / len(x))
    
    # Pairwise correlations
    corr_xy = float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 1e-8 and np.std(y) > 1e-8 else 0.0
    corr_xz = float(np.corrcoef(x, z)[0, 1]) if np.std(x) > 1e-8 and np.std(z) > 1e-8 else 0.0
    corr_yz = float(np.corrcoef(y, z)[0, 1]) if np.std(y) > 1e-8 and np.std(z) > 1e-8 else 0.0
    
    if np.isnan(corr_xy): corr_xy = 0.0
    if np.isnan(corr_xz): corr_xz = 0.0
    if np.isnan(corr_yz): corr_yz = 0.0
    
    # Jerk features
    dt = 1.0 / fs
    jerk_x = np.diff(x) / dt if len(x) > 1 else np.array([0.0])
    jerk_y = np.diff(y) / dt if len(y) > 1 else np.array([0.0])
    jerk_z = np.diff(z) / dt if len(z) > 1 else np.array([0.0])
    
    jerk_feats = [
        float(np.mean(jerk_x)), float(np.mean(jerk_y)), float(np.mean(jerk_z)),
        float(np.std(jerk_x)), float(np.std(jerk_y)), float(np.std(jerk_z))
    ]
    
    all_features = (
        feat_x + feat_y + feat_z + feat_mag + 
        [sma, corr_xy, corr_xz, corr_yz] + 
        jerk_feats
    )
    
    return np.array([all_features], dtype=np.float64)
