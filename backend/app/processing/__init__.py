"""Processing module"""
from .preprocessing import PreprocessingPipeline
from .features import FeatureExtractor
from .visualization import (
    generate_preprocessing_plots,
    plot_psd_heatmap,
    plot_band_power_violin,
    plot_confusion_matrix,
    plot_roc_curve,
    plot_feature_importance
)

__all__ = [
    'PreprocessingPipeline',
    'FeatureExtractor',
    'generate_preprocessing_plots',
    'plot_psd_heatmap',
    'plot_band_power_violin',
    'plot_confusion_matrix',
    'plot_roc_curve',
    'plot_feature_importance'
]
