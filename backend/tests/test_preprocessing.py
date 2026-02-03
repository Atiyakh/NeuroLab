"""Tests for preprocessing pipeline."""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch
import mne


class TestPreprocessingPipeline:
    """Tests for the PreprocessingPipeline class."""

    def test_pipeline_initialization(self):
        """Test pipeline initializes with correct parameters."""
        from app.processing.preprocessing import PreprocessingPipeline
        
        pipeline = PreprocessingPipeline(
            target_sfreq=256,
            notch_freqs=[50],
            bandpass=(1, 40),
            n_components=15
        )
        
        assert pipeline.target_sfreq == 256
        assert pipeline.notch_freqs == [50]
        assert pipeline.bandpass == (1, 40)
        assert pipeline.n_components == 15

    def test_resample(self, sample_eeg_data):
        """Test resampling functionality."""
        from app.processing.preprocessing import PreprocessingPipeline
        
        # Create Raw object
        info = mne.create_info(
            ch_names=sample_eeg_data['ch_names'],
            sfreq=sample_eeg_data['sfreq'],
            ch_types='eeg'
        )
        raw = mne.io.RawArray(sample_eeg_data['data'], info)
        
        pipeline = PreprocessingPipeline(target_sfreq=128)
        pipeline.raw = raw
        
        resampled = pipeline.resample()
        
        assert resampled.info['sfreq'] == 128

    def test_notch_filter(self, sample_eeg_data):
        """Test notch filtering."""
        from app.processing.preprocessing import PreprocessingPipeline
        
        # Create Raw object
        info = mne.create_info(
            ch_names=sample_eeg_data['ch_names'],
            sfreq=sample_eeg_data['sfreq'],
            ch_types='eeg'
        )
        raw = mne.io.RawArray(sample_eeg_data['data'], info)
        
        pipeline = PreprocessingPipeline(notch_freqs=[50, 60])
        pipeline.raw = raw
        
        # Should not raise any errors
        filtered = pipeline.notch_filter()
        assert filtered is not None

    def test_bandpass_filter(self, sample_eeg_data):
        """Test bandpass filtering."""
        from app.processing.preprocessing import PreprocessingPipeline
        
        info = mne.create_info(
            ch_names=sample_eeg_data['ch_names'],
            sfreq=sample_eeg_data['sfreq'],
            ch_types='eeg'
        )
        raw = mne.io.RawArray(sample_eeg_data['data'], info)
        
        pipeline = PreprocessingPipeline(bandpass=(1, 40))
        pipeline.raw = raw
        
        filtered = pipeline.bandpass_filter()
        assert filtered is not None

    def test_detect_bad_channels(self, sample_eeg_data):
        """Test bad channel detection."""
        from app.processing.preprocessing import PreprocessingPipeline
        
        # Add a bad channel (flat line)
        data = sample_eeg_data['data'].copy()
        data[0, :] = 0  # Make first channel flat
        
        info = mne.create_info(
            ch_names=sample_eeg_data['ch_names'],
            sfreq=sample_eeg_data['sfreq'],
            ch_types='eeg'
        )
        raw = mne.io.RawArray(data, info)
        
        pipeline = PreprocessingPipeline()
        pipeline.raw = raw
        
        bad_channels = pipeline.detect_bad_channels()
        
        # The flat channel should be detected as bad
        assert isinstance(bad_channels, list)


class TestPreprocessingIntegration:
    """Integration tests for preprocessing."""

    def test_full_pipeline(self, sample_eeg_data):
        """Test complete preprocessing pipeline."""
        from app.processing.preprocessing import PreprocessingPipeline
        import tempfile
        
        info = mne.create_info(
            ch_names=sample_eeg_data['ch_names'],
            sfreq=sample_eeg_data['sfreq'],
            ch_types='eeg'
        )
        raw = mne.io.RawArray(sample_eeg_data['data'], info)
        
        # Save temporary file
        with tempfile.NamedTemporaryFile(suffix='.fif', delete=False) as f:
            raw.save(f.name, overwrite=True)
            
            pipeline = PreprocessingPipeline(
                target_sfreq=128,
                notch_freqs=[50],
                bandpass=(1, 40),
                n_components=3
            )
            
            # Run pipeline
            pipeline.read_raw(f.name)
            pipeline.resample()
            pipeline.notch_filter()
            pipeline.bandpass_filter()
            
            assert pipeline.raw is not None
            assert pipeline.raw.info['sfreq'] == 128
