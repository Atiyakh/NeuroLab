"""Tests for feature extraction module."""

import pytest
import numpy as np
import mne


class TestFeatureExtractor:
    """Tests for the FeatureExtractor class."""

    def test_extractor_initialization(self):
        """Test feature extractor initializes correctly."""
        from app.processing.features import FeatureExtractor
        
        extractor = FeatureExtractor(sfreq=256)
        
        assert extractor.sfreq == 256
        assert hasattr(extractor, 'bands')
        assert 'alpha' in extractor.bands

    def test_compute_band_powers(self, sample_eeg_data):
        """Test band power computation."""
        from app.processing.features import FeatureExtractor
        
        extractor = FeatureExtractor(sfreq=sample_eeg_data['sfreq'])
        
        band_powers = extractor.compute_band_powers(
            sample_eeg_data['data'],
            sample_eeg_data['ch_names']
        )
        
        assert isinstance(band_powers, dict)
        assert len(band_powers) == len(sample_eeg_data['ch_names'])
        
        # Check that all bands are present
        for ch in sample_eeg_data['ch_names']:
            assert ch in band_powers
            assert 'delta' in band_powers[ch]
            assert 'theta' in band_powers[ch]
            assert 'alpha' in band_powers[ch]
            assert 'beta' in band_powers[ch]
            assert 'gamma' in band_powers[ch]

    def test_compute_relative_powers(self, sample_eeg_data):
        """Test relative power computation."""
        from app.processing.features import FeatureExtractor
        
        extractor = FeatureExtractor(sfreq=sample_eeg_data['sfreq'])
        
        band_powers = extractor.compute_band_powers(
            sample_eeg_data['data'],
            sample_eeg_data['ch_names']
        )
        
        relative_powers = extractor.compute_relative_powers(band_powers)
        
        # Check that relative powers sum to approximately 1
        for ch in sample_eeg_data['ch_names']:
            total = sum(relative_powers[ch].values())
            assert 0.99 < total < 1.01

    def test_compute_time_domain_stats(self, sample_eeg_data):
        from app.processing.features import FeatureExtractor
        
        extractor = FeatureExtractor(sfreq=sample_eeg_data['sfreq'])
        
        stats = extractor.compute_time_domain_stats(
            sample_eeg_data['data'],
            sample_eeg_data['ch_names']
        )
        
        assert isinstance(stats, dict)
        for ch in sample_eeg_data['ch_names']:
            assert ch in stats
            assert 'mean' in stats[ch]
            assert 'std' in stats[ch]
            assert 'variance' in stats[ch]
            assert 'skewness' in stats[ch]
            assert 'kurtosis' in stats[ch]

    def test_compute_hjorth_parameters(self, sample_eeg_data):
        from app.processing.features import FeatureExtractor
        
        extractor = FeatureExtractor(sfreq=sample_eeg_data['sfreq'])
        
        hjorth = extractor.compute_hjorth_parameters(
            sample_eeg_data['data'],
            sample_eeg_data['ch_names']
        )
        
        assert isinstance(hjorth, dict)
        for ch in sample_eeg_data['ch_names']:
            assert ch in hjorth
            assert 'activity' in hjorth[ch]
            assert 'mobility' in hjorth[ch]
            assert 'complexity' in hjorth[ch]
            
            # Hjorth parameters should be positive
            assert hjorth[ch]['activity'] >= 0
            assert hjorth[ch]['mobility'] >= 0
            assert hjorth[ch]['complexity'] >= 0

    def test_extract_all_features(self, sample_eeg_data):
        from app.processing.features import FeatureExtractor
        
        extractor = FeatureExtractor(sfreq=sample_eeg_data['sfreq'])
        
        features = extractor.extract_all(
            sample_eeg_data['data'],
            sample_eeg_data['ch_names']
        )
        
        assert 'band_powers' in features
        assert 'relative_powers' in features
        assert 'time_stats' in features
        assert 'hjorth' in features


class TestFeatureExtractionEdgeCases:

    def test_empty_data(self):
        from app.processing.features import FeatureExtractor
        
        extractor = FeatureExtractor(sfreq=256)
        
        with pytest.raises(Exception):
            extractor.compute_band_powers(
                np.array([[]]),
                []
            )

    def test_single_channel(self):
        from app.processing.features import FeatureExtractor
        
        extractor = FeatureExtractor(sfreq=256)
        
        # Generate single channel data
        data = np.random.randn(1, 2560) * 1e-6
        ch_names = ['Cz']
        
        band_powers = extractor.compute_band_powers(data, ch_names)
        
        assert 'Cz' in band_powers
        assert len(band_powers) == 1

    def test_short_epoch(self):
        from app.processing.features import FeatureExtractor
        
        extractor = FeatureExtractor(sfreq=256)
        
        # 0.5 second epoch
        data = np.random.randn(6, 128) * 1e-6
        ch_names = ['Fp1', 'Fp2', 'Cz', 'Pz', 'O1', 'O2']
        
        # Should still work but with limited frequency resolution
        band_powers = extractor.compute_band_powers(data, ch_names)
        assert band_powers is not None
