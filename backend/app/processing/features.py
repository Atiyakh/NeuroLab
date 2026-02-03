"""
Feature Extraction Module
Explicit implementation of all features from design doc
"""
import numpy as np
from scipy import signal, stats
import mne
import pandas as pd


class FeatureExtractor:
    """
    Extract features from EEG data.
    
    Features:
    - PSD / Band power (Welch)
    - Relative band power
    - Time-domain stats (mean, std, skew, kurtosis, RMS)
    - Hjorth parameters (activity, mobility, complexity)
    - Entropy metrics (sample entropy)
    - Connectivity (coherence) - optional
    """
    
    def __init__(self, config: dict = None):
        """
        Initialize feature extractor.
        
        Args:
            config: Feature extraction configuration
        """
        self.config = config or {}
        
        # Default bands from design doc
        self.bands = self.config.get('bands', [
            {'name': 'delta', 'low': 1, 'high': 4},
            {'name': 'theta', 'low': 4, 'high': 8},
            {'name': 'alpha', 'low': 8, 'high': 12},
            {'name': 'beta', 'low': 12, 'high': 30},
            {'name': 'gamma', 'low': 30, 'high': 45}
        ])
        
        self.welch_window_sec = self.config.get('welch_window_sec', 2.0)
        self.entropy_m = self.config.get('entropy_m', 2)
        self.entropy_r_factor = self.config.get('entropy_r_factor', 0.2)
    
    def extract_all_features(
        self,
        raw: mne.io.Raw,
        epoch_length: float = 2.0,
        overlap: float = 0.5
    ) -> pd.DataFrame:
        """
        Extract all features from raw data.
        
        Creates epochs and computes features for each epoch/channel.
        
        Args:
            raw: MNE Raw object
            epoch_length: Epoch length in seconds
            overlap: Overlap fraction
            
        Returns:
            DataFrame with features per epoch per channel
        """
        sfreq = raw.info['sfreq']
        data = raw.get_data()
        ch_names = raw.ch_names
        
        # Create epochs
        step = int(epoch_length * (1 - overlap) * sfreq)
        epoch_samples = int(epoch_length * sfreq)
        
        n_epochs = (data.shape[1] - epoch_samples) // step + 1
        
        all_features = []
        
        for epoch_idx in range(n_epochs):
            start = epoch_idx * step
            end = start + epoch_samples
            
            if end > data.shape[1]:
                break
            
            epoch_data = data[:, start:end]
            
            for ch_idx, ch_name in enumerate(ch_names):
                ch_data = epoch_data[ch_idx]
                
                # Extract features for this channel/epoch
                features = {'epoch_id': epoch_idx, 'channel': ch_name}
                
                # Band powers
                band_powers = self._compute_band_powers(ch_data, sfreq)
                features.update(band_powers)
                
                # Relative band powers
                rel_powers = self._compute_relative_band_powers(band_powers)
                features.update(rel_powers)
                
                # Time-domain stats
                time_features = self._compute_time_features(ch_data)
                features.update(time_features)
                
                # Hjorth parameters
                hjorth = self._compute_hjorth(ch_data)
                features.update(hjorth)
                
                # Entropy
                entropy = self._compute_sample_entropy(ch_data)
                features['sample_entropy'] = entropy
                
                all_features.append(features)
        
        df = pd.DataFrame(all_features)
        return df
    
    def extract_channel_averaged_features(
        self,
        raw: mne.io.Raw,
        epoch_length: float = 2.0,
        overlap: float = 0.5
    ) -> pd.DataFrame:
        """
        Extract features averaged across channels.
        
        Useful for simpler models that don't need per-channel features.
        
        Args:
            raw: MNE Raw object
            epoch_length: Epoch length in seconds
            overlap: Overlap fraction
            
        Returns:
            DataFrame with averaged features per epoch
        """
        per_channel_df = self.extract_all_features(raw, epoch_length, overlap)
        
        # Group by epoch and compute mean across channels
        feature_cols = [c for c in per_channel_df.columns if c not in ['epoch_id', 'channel']]
        
        averaged = per_channel_df.groupby('epoch_id')[feature_cols].mean().reset_index()
        
        return averaged
    
    def _compute_band_powers(self, data: np.ndarray, sfreq: float) -> dict:
        """
        Compute band powers using Welch's method.
        
        Args:
            data: 1D signal array
            sfreq: Sampling frequency
            
        Returns:
            Dict of band powers
        """
        # Welch parameters from design doc
        nperseg = int(self.welch_window_sec * sfreq)
        noverlap = nperseg // 2
        
        freqs, psd = signal.welch(
            data,
            fs=sfreq,
            nperseg=nperseg,
            noverlap=noverlap
        )
        
        band_powers = {}
        
        for band in self.bands:
            name = band['name']
            low = band['low']
            high = band['high']
            
            # Find frequency indices
            idx = np.logical_and(freqs >= low, freqs <= high)
            
            # Integrate PSD in band (mean power)
            band_power = np.trapz(psd[idx], freqs[idx])
            band_powers[f'band_{name}'] = band_power
        
        # Total power (1-45 Hz)
        total_idx = np.logical_and(freqs >= 1, freqs <= 45)
        band_powers['total_power'] = np.trapz(psd[total_idx], freqs[total_idx])
        
        return band_powers
    
    def _compute_relative_band_powers(self, band_powers: dict) -> dict:
        """
        Compute relative band powers (normalized by total).
        
        Args:
            band_powers: Dict from _compute_band_powers
            
        Returns:
            Dict of relative powers
        """
        total = band_powers.get('total_power', 1e-10)
        
        rel_powers = {}
        for band in self.bands:
            name = band['name']
            key = f'band_{name}'
            if key in band_powers:
                rel_powers[f'rel_{name}'] = band_powers[key] / total
        
        return rel_powers
    
    def _compute_time_features(self, data: np.ndarray) -> dict:
        """
        Compute time-domain statistical features.
        
        Args:
            data: 1D signal array
            
        Returns:
            Dict of features
        """
        return {
            'mean': np.mean(data),
            'std': np.std(data),
            'skewness': stats.skew(data),
            'kurtosis': stats.kurtosis(data),
            'rms': np.sqrt(np.mean(data ** 2)),
            'peak_to_peak': np.ptp(data),
            'zero_crossings': np.sum(np.diff(np.sign(data)) != 0)
        }
    
    def _compute_hjorth(self, data: np.ndarray) -> dict:
        """
        Compute Hjorth parameters.
        
        - Activity: variance of signal
        - Mobility: sqrt(var(derivative) / var(signal))
        - Complexity: mobility(derivative) / mobility(signal)
        
        Args:
            data: 1D signal array
            
        Returns:
            Dict with activity, mobility, complexity
        """
        # First derivative
        d1 = np.diff(data)
        # Second derivative
        d2 = np.diff(d1)
        
        # Activity
        activity = np.var(data)
        
        # Mobility
        mobility = np.sqrt(np.var(d1) / (activity + 1e-10))
        
        # Complexity
        mobility_d1 = np.sqrt(np.var(d2) / (np.var(d1) + 1e-10))
        complexity = mobility_d1 / (mobility + 1e-10)
        
        return {
            'hjorth_activity': activity,
            'hjorth_mobility': mobility,
            'hjorth_complexity': complexity
        }
    
    def _compute_sample_entropy(self, data: np.ndarray, m: int = None, r: float = None) -> float:
        """
        Compute sample entropy.
        
        Args:
            data: 1D signal array
            m: Embedding dimension (default from config)
            r: Tolerance (default: r_factor * std)
            
        Returns:
            Sample entropy value
        """
        if m is None:
            m = self.entropy_m
        if r is None:
            r = self.entropy_r_factor * np.std(data)
        
        N = len(data)
        
        if N < m + 2:
            return 0.0
        
        # Create template vectors
        def _count_matches(template_length):
            templates = np.array([data[i:i + template_length] for i in range(N - template_length)])
            count = 0
            for i in range(len(templates)):
                for j in range(i + 1, len(templates)):
                    if np.max(np.abs(templates[i] - templates[j])) < r:
                        count += 2  # Count both (i,j) and (j,i)
            return count
        
        # Count matches for m and m+1
        B = _count_matches(m)
        A = _count_matches(m + 1)
        
        # Avoid log(0)
        if B == 0 or A == 0:
            return 0.0
        
        return -np.log(A / B)
    
    def compute_connectivity(
        self,
        raw: mne.io.Raw,
        channel_pairs: list = None
    ) -> dict:
        """
        Compute connectivity (coherence) between channel pairs.
        
        Args:
            raw: MNE Raw object
            channel_pairs: List of (ch1, ch2) tuples. If None, uses defaults.
            
        Returns:
            Dict of coherence values per band per pair
        """
        if channel_pairs is None:
            # Default pairs: frontal-parietal
            channel_pairs = [('Fz', 'Pz'), ('F3', 'P3'), ('F4', 'P4')]
        
        sfreq = raw.info['sfreq']
        data = raw.get_data()
        ch_names = list(raw.ch_names)
        
        connectivity = {}
        
        for ch1, ch2 in channel_pairs:
            if ch1 not in ch_names or ch2 not in ch_names:
                continue
            
            idx1 = ch_names.index(ch1)
            idx2 = ch_names.index(ch2)
            
            # Compute coherence
            freqs, coh = signal.coherence(
                data[idx1],
                data[idx2],
                fs=sfreq,
                nperseg=int(self.welch_window_sec * sfreq)
            )
            
            pair_name = f'{ch1}_{ch2}'
            
            # Average coherence in each band
            for band in self.bands:
                idx = np.logical_and(freqs >= band['low'], freqs <= band['high'])
                connectivity[f'coh_{pair_name}_{band["name"]}'] = np.mean(coh[idx])
        
        return connectivity


def extract_features_from_raw(raw: mne.io.Raw, config: dict = None) -> pd.DataFrame:
    """
    Convenience function to extract features from raw data.
    
    Args:
        raw: MNE Raw object
        config: Feature extraction config
        
    Returns:
        DataFrame with features
    """
    extractor = FeatureExtractor(config)
    return extractor.extract_all_features(raw)


def create_feature_matrix(
    feature_df: pd.DataFrame,
    aggregate: str = 'mean'
) -> tuple:
    """
    Create feature matrix for ML from feature DataFrame.
    
    Args:
        feature_df: DataFrame from FeatureExtractor
        aggregate: How to aggregate across epochs ('mean', 'median', 'all')
        
    Returns:
        Tuple of (feature_matrix, feature_names)
    """
    feature_cols = [c for c in feature_df.columns if c not in ['epoch_id', 'channel', 'label']]
    
    if aggregate == 'all':
        # Flatten all epochs
        X = feature_df[feature_cols].values
    elif aggregate == 'mean':
        X = feature_df.groupby('epoch_id')[feature_cols].mean().values
    elif aggregate == 'median':
        X = feature_df.groupby('epoch_id')[feature_cols].median().values
    else:
        raise ValueError(f"Unknown aggregate method: {aggregate}")
    
    return X, feature_cols
