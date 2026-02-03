import numpy as np
import mne
from scipy import stats


class PreprocessingPipeline:
    """MNE Preprocessing Pipeline"""
    def __init__(self, config: dict = None):
        """
        Initialize pipeline with configuration.
        
        Args:
            config: Processing configuration dict
        """
        self.config = config or {}
        
        # Defaults from design doc
        self.target_sfreq = self.config.get('target_sfreq', 250)
        self.notch_freqs = self.config.get('notch_freqs', [50])
        self.bandpass = self.config.get('bandpass', {'low': 1.0, 'high': 40.0})
        self.ica_config = self.config.get('ica', {
            'n_components': 20,
            'method': 'fastica',
            'random_state': 42,
            'eog_corr_threshold': 0.35,
            'ecg_corr_threshold': 0.3
        })
        self.artifact_config = self.config.get('artifact', {
            'flat_threshold': 1e-6,
            'high_variance_zscore': 5,
            'kurtosis_threshold': 10
        })
    
    def read_raw(self, file_path: str) -> mne.io.Raw:
        """
        Read raw EEG/MEG file.
        
        Supports: EDF, BDF, FIF, EEGLAB SET
        
        Args:
            file_path: Path to raw file
            
        Returns:
            MNE Raw object
        """
        ext = file_path.lower().rsplit('.', 1)[-1]
        
        if ext == 'edf':
            raw = mne.io.read_raw_edf(file_path, preload=True)
        elif ext == 'bdf':
            raw = mne.io.read_raw_bdf(file_path, preload=True)
        elif ext == 'fif':
            raw = mne.io.read_raw_fif(file_path, preload=True)
        elif ext == 'set':
            raw = mne.io.read_raw_eeglab(file_path, preload=True)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
        
        # Try to set standard montage
        try:
            # Normalize channel names first
            raw = self._normalize_channel_names(raw)
            raw.set_montage('standard_1020', on_missing='ignore')
        except Exception:
            pass  # Continue without montage if it fails
        
        return raw
    
    def _normalize_channel_names(self, raw: mne.io.Raw) -> mne.io.Raw:
        """
        Normalize channel names for standard_1020 compatibility.
        
        - Uppercase
        - Replace dashes and spaces with underscores
        - Handle common variations (FP1 -> Fp1)
        """
        # Standard 10-20 channel mapping for case-insensitive matching
        standard_names = [
            'Fp1', 'Fp2', 'F7', 'F3', 'Fz', 'F4', 'F8',
            'T7', 'C3', 'Cz', 'C4', 'T8',
            'P7', 'P3', 'Pz', 'P4', 'P8',
            'O1', 'Oz', 'O2',
            'FC1', 'FC2', 'FC5', 'FC6',
            'CP1', 'CP2', 'CP5', 'CP6',
            'AF3', 'AF4', 'AF7', 'AF8',
            'PO3', 'PO4', 'PO7', 'PO8'
        ]
        
        name_mapping = {name.upper(): name for name in standard_names}
        
        rename_dict = {}
        for ch_name in raw.ch_names:
            # Clean up name
            clean_name = ch_name.upper().replace('-', '').replace(' ', '').replace('_', '')
            
            # Check for standard match
            if clean_name in name_mapping:
                rename_dict[ch_name] = name_mapping[clean_name]
            # Handle FP vs Fp
            elif clean_name.startswith('FP') and 'FP' + clean_name[2:] in name_mapping:
                rename_dict[ch_name] = name_mapping['FP' + clean_name[2:]]
        
        if rename_dict:
            raw.rename_channels(rename_dict)
        
        return raw
    
    def resample(self, raw: mne.io.Raw) -> mne.io.Raw:
        """
        Resample to target sampling frequency.
        
        Args:
            raw: MNE Raw object
            
        Returns:
            Resampled Raw object
        """
        if raw.info['sfreq'] != self.target_sfreq:
            raw.resample(self.target_sfreq, npad="auto")
        return raw
    
    def notch_filter(self, raw: mne.io.Raw) -> mne.io.Raw:
        """
        Apply notch filter to remove line noise.
        
        Args:
            raw: MNE Raw object
            
        Returns:
            Filtered Raw object
        """
        raw.notch_filter(
            self.notch_freqs,
            fir_design='firwin',
            verbose=False
        )
        return raw
    
    def bandpass_filter(self, raw: mne.io.Raw) -> mne.io.Raw:
        """
        Apply bandpass filter.
        
        Uses FIR filter with zero-phase.
        FIR order heuristic: int(0.3 * sfreq)
        
        Args:
            raw: MNE Raw object
            
        Returns:
            Filtered Raw object
        """
        raw.filter(
            l_freq=self.bandpass['low'],
            h_freq=self.bandpass['high'],
            fir_design='firwin',
            pad='reflect_limited',
            verbose=False
        )
        return raw
    
    def detect_bad_channels(self, raw: mne.io.Raw) -> tuple:
        """
        Detect bad channels using multiple metrics.
        
        Metrics:
        - Flat channels: std < threshold
        - High variance: Z-score > threshold
        - High kurtosis: > threshold
        
        Args:
            raw: MNE Raw object
            
        Returns:
            Tuple of (raw with bads marked, list of bad channel names)
        """
        data = raw.get_data()
        bad_channels = []
        
        flat_threshold = self.artifact_config.get('flat_threshold', 1e-6)
        zscore_threshold = self.artifact_config.get('high_variance_zscore', 5)
        kurtosis_threshold = self.artifact_config.get('kurtosis_threshold', 10)
        
        # Get only EEG channels
        eeg_picks = mne.pick_types(raw.info, eeg=True, exclude=[])
        
        for idx in eeg_picks:
            ch_name = raw.ch_names[idx]
            ch_data = data[idx]
            
            # Flat channel detection
            if np.std(ch_data) < flat_threshold:
                bad_channels.append(ch_name)
                continue
            
            # Kurtosis check
            kurt = stats.kurtosis(ch_data)
            if kurt > kurtosis_threshold:
                bad_channels.append(ch_name)
                continue
        
        # High variance (Z-score across channels)
        if len(eeg_picks) > 1:
            channel_vars = np.var(data[eeg_picks], axis=1)
            z_scores = stats.zscore(channel_vars)
            
            for i, idx in enumerate(eeg_picks):
                if abs(z_scores[i]) > zscore_threshold:
                    ch_name = raw.ch_names[idx]
                    if ch_name not in bad_channels:
                        bad_channels.append(ch_name)
        
        # Mark bad channels in raw
        raw.info['bads'].extend(bad_channels)
        raw.info['bads'] = list(set(raw.info['bads']))  # Remove duplicates
        
        return raw, bad_channels
    
    def interpolate_bads(self, raw: mne.io.Raw) -> mne.io.Raw:
        """
        Interpolate bad channels.
        
        Args:
            raw: MNE Raw object with bads marked
            
        Returns:
            Raw object with interpolated channels
        """
        if raw.info['bads']:
            raw.interpolate_bads(reset_bads=True, verbose=False)
        return raw
    
    def run_ica(self, raw: mne.io.Raw) -> tuple:
        """
        Run ICA for artifact removal.
        
        Uses FastICA, detects EOG and ECG artifacts.
        
        Args:
            raw: MNE Raw object
            
        Returns:
            Tuple of (cleaned raw, ICA info dict)
        """
        n_components = self.ica_config.get('n_components', 20)
        method = self.ica_config.get('method', 'fastica')
        random_state = self.ica_config.get('random_state', 42)
        eog_threshold = self.ica_config.get('eog_corr_threshold', 0.35)
        ecg_threshold = self.ica_config.get('ecg_corr_threshold', 0.3)
        
        # Ensure n_components doesn't exceed rank
        rank = mne.compute_rank(raw, rank='info')
        max_components = min(n_components, sum(rank.values()) - 1)
        
        ica = mne.preprocessing.ICA(
            n_components=max_components,
            method=method,
            random_state=random_state,
            max_iter=500
        )
        
        # Fit ICA
        ica.fit(raw)
        
        ica_info = {
            'n_components': ica.n_components_,
            'method': method,
            'excluded_components': [],
            'eog_scores': [],
            'ecg_scores': []
        }
        
        # Find EOG artifacts
        try:
            # Try to find EOG channels or use frontal channels
            eog_inds, eog_scores = ica.find_bads_eog(
                raw,
                threshold=eog_threshold
            )
            ica.exclude.extend(eog_inds)
            ica_info['eog_indices'] = eog_inds
            ica_info['eog_scores'] = eog_scores.tolist() if hasattr(eog_scores, 'tolist') else list(eog_scores)
        except Exception:
            # No EOG channels found
            pass
        
        # Find ECG artifacts if ECG channel exists
        try:
            ecg_inds, ecg_scores = ica.find_bads_ecg(
                raw,
                threshold=ecg_threshold
            )
            ica.exclude.extend(ecg_inds)
            ica_info['ecg_indices'] = ecg_inds
            ica_info['ecg_scores'] = ecg_scores.tolist() if hasattr(ecg_scores, 'tolist') else list(ecg_scores)
        except Exception:
            # No ECG channel found
            pass
        
        # Remove duplicates from exclude list
        ica.exclude = list(set(ica.exclude))
        ica_info['excluded_components'] = ica.exclude
        
        # Apply ICA
        raw_clean = ica.apply(raw.copy())
        
        return raw_clean, ica_info
    
    def detect_muscle_artifacts(self, raw: mne.io.Raw, window_sec: float = 0.5) -> list:
        """
        Detect muscle/high-frequency artifacts.
        
        Computes power in 20-40Hz band in sliding windows.
        
        Args:
            raw: MNE Raw object
            window_sec: Window size in seconds
            
        Returns:
            List of (start_time, end_time) tuples for bad segments
        """
        threshold = self.artifact_config.get('muscle_rms_threshold', 100e-6)
        
        # Filter to muscle frequency range
        raw_filt = raw.copy().filter(20, 40, verbose=False)
        data = raw_filt.get_data()
        
        sfreq = raw.info['sfreq']
        window_samples = int(window_sec * sfreq)
        
        bad_segments = []
        
        for start in range(0, data.shape[1] - window_samples, window_samples):
            end = start + window_samples
            window_data = data[:, start:end]
            
            # Compute RMS across channels
            rms = np.sqrt(np.mean(window_data ** 2))
            
            if rms > threshold:
                start_time = start / sfreq
                end_time = end / sfreq
                bad_segments.append((start_time, end_time))
        
        return bad_segments
    
    def create_epochs(
        self,
        raw: mne.io.Raw,
        epoch_length: float = 2.0,
        overlap: float = 0.5,
        baseline: tuple = None
    ) -> mne.Epochs:
        """Returns MNE Epochs object"""
        # create events at regular intervals
        duration = raw.times[-1]
        step = epoch_length * (1 - overlap)
        n_epochs = int((duration - epoch_length) / step) + 1
        
        events = np.zeros((n_epochs, 3), dtype=int)
        sfreq = raw.info['sfreq']
        
        for i in range(n_epochs):
            events[i, 0] = int(i * step * sfreq)
            events[i, 2] = 1  # Event ID
        
        epochs = mne.Epochs(
            raw,
            events,
            event_id={'epoch': 1},
            tmin=0,
            tmax=epoch_length,
            baseline=baseline,
            preload=True,
            verbose=False
        )
        
        return epochs
