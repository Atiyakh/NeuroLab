"""
Visualization generation for preprocessing and analysis
Uses seaborn for static plots (server-side rendering)
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server
import matplotlib.pyplot as plt
import seaborn as sns
import mne


def generate_preprocessing_plots(
    raw: mne.io.Raw,
    recording_id: str,
    output_dir: str,
    storage_service,
    ica_info: dict = None
) -> dict:
    """
    Generate all preprocessing visualizations.
    
    Creates:
    - PSD heatmap (channels × freq)
    - Raw traces sample
    - Band power distribution
    - ICA components (if available)
    
    Args:
        raw: Processed MNE Raw object
        recording_id: Recording ID for naming
        output_dir: Local temp directory
        storage_service: S3 storage service
        ica_info: ICA processing info dict
        
    Returns:
        Dict of visualization paths in S3
    """
    viz_paths = {}
    s3_prefix = f"visualizations/{recording_id}"
    
    # Set seaborn style
    sns.set_theme(style="whitegrid", palette="husl")
    
    # 1. PSD Heatmap
    try:
        fig = plot_psd_heatmap(raw)
        local_path = os.path.join(output_dir, 'psd_heatmap.png')
        fig.savefig(local_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        s3_path = f"{s3_prefix}/psd_heatmap.png"
        storage_service.upload_file(local_path, s3_path, content_type='image/png')
        viz_paths['psd_heatmap'] = s3_path
    except Exception as e:
        print(f"Error generating PSD heatmap: {e}")
    
    # 2. Raw traces sample
    try:
        fig = plot_raw_traces(raw, duration=10)
        local_path = os.path.join(output_dir, 'cleaned_traces.png')
        fig.savefig(local_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        s3_path = f"{s3_prefix}/cleaned_traces.png"
        storage_service.upload_file(local_path, s3_path, content_type='image/png')
        viz_paths['cleaned_traces'] = s3_path
    except Exception as e:
        print(f"Error generating traces: {e}")
    
    # 3. Band power violin plot
    try:
        fig = plot_band_power_violin(raw)
        local_path = os.path.join(output_dir, 'band_power_violin.png')
        fig.savefig(local_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        s3_path = f"{s3_prefix}/band_power_violin.png"
        storage_service.upload_file(local_path, s3_path, content_type='image/png')
        viz_paths['band_power_violin'] = s3_path
    except Exception as e:
        print(f"Error generating band power plot: {e}")
    
    # 4. Topomap (if montage available)
    try:
        if raw.get_montage() is not None:
            fig = plot_topomap(raw)
            local_path = os.path.join(output_dir, 'topomap.png')
            fig.savefig(local_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            
            s3_path = f"{s3_prefix}/topomap.png"
            storage_service.upload_file(local_path, s3_path, content_type='image/png')
            viz_paths['topomap'] = s3_path
    except Exception as e:
        print(f"Error generating topomap: {e}")
    
    return viz_paths


def plot_psd_heatmap(raw: mne.io.Raw, fmin: float = 1, fmax: float = 45) -> plt.Figure:
    """
    Create PSD heatmap (channels × frequency).
    
    Args:
        raw: MNE Raw object
        fmin: Minimum frequency
        fmax: Maximum frequency
        
    Returns:
        Matplotlib figure
    """
    # Compute PSD
    spectrum = raw.compute_psd(method='welch', fmin=fmin, fmax=fmax, verbose=False)
    psds, freqs = spectrum.get_data(return_freqs=True)
    
    # Convert to dB
    psds_db = 10 * np.log10(psds)
    
    # Get channel names (limit to first 32 for readability)
    ch_names = raw.ch_names[:32] if len(raw.ch_names) > 32 else raw.ch_names
    psds_db = psds_db[:len(ch_names)]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create heatmap
    im = ax.imshow(
        psds_db,
        aspect='auto',
        origin='lower',
        cmap='viridis',
        extent=[freqs[0], freqs[-1], 0, len(ch_names)]
    )
    
    ax.set_xlabel('Frequency (Hz)', fontsize=12)
    ax.set_ylabel('Channel', fontsize=12)
    ax.set_title('Power Spectral Density', fontsize=14)
    
    # Set y-ticks to channel names
    ax.set_yticks(np.arange(len(ch_names)) + 0.5)
    ax.set_yticklabels(ch_names, fontsize=8)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Power (dB)', fontsize=10)
    
    plt.tight_layout()
    return fig


def plot_raw_traces(raw: mne.io.Raw, duration: float = 10, n_channels: int = 8) -> plt.Figure:
    """
    Plot sample of raw traces.
    
    Args:
        raw: MNE Raw object
        duration: Duration to plot in seconds
        n_channels: Number of channels to show
        
    Returns:
        Matplotlib figure
    """
    # Get data for first N channels
    picks = mne.pick_types(raw.info, eeg=True, exclude=[])[:n_channels]
    
    start_sample = 0
    end_sample = min(int(duration * raw.info['sfreq']), raw.n_times)
    
    data = raw.get_data(picks=picks, start=start_sample, stop=end_sample)
    times = raw.times[start_sample:end_sample]
    
    # Create figure
    fig, axes = plt.subplots(n_channels, 1, figsize=(14, 2 * n_channels), sharex=True)
    if n_channels == 1:
        axes = [axes]
    
    for i, (ax, pick) in enumerate(zip(axes, picks)):
        ch_name = raw.ch_names[pick]
        ax.plot(times, data[i] * 1e6, linewidth=0.5, color=sns.color_palette()[i % 10])
        ax.set_ylabel(f'{ch_name}\n(µV)', fontsize=9)
        ax.set_xlim(times[0], times[-1])
        
        # Remove top and right spines
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    
    axes[-1].set_xlabel('Time (s)', fontsize=12)
    fig.suptitle('EEG Traces (Cleaned)', fontsize=14, y=1.02)
    
    plt.tight_layout()
    return fig


def plot_band_power_violin(raw: mne.io.Raw) -> plt.Figure:
    """
    Create violin plot of band powers across channels.
    
    Args:
        raw: MNE Raw object
        
    Returns:
        Matplotlib figure
    """
    bands = {
        'Delta\n(1-4 Hz)': (1, 4),
        'Theta\n(4-8 Hz)': (4, 8),
        'Alpha\n(8-12 Hz)': (8, 12),
        'Beta\n(12-30 Hz)': (12, 30),
        'Gamma\n(30-45 Hz)': (30, 45)
    }
    
    # Compute PSD
    spectrum = raw.compute_psd(method='welch', fmin=1, fmax=45, verbose=False)
    psds, freqs = spectrum.get_data(return_freqs=True)
    
    # Calculate band powers
    band_powers = {}
    for band_name, (fmin, fmax) in bands.items():
        freq_mask = (freqs >= fmin) & (freqs <= fmax)
        band_power = psds[:, freq_mask].mean(axis=1)
        band_powers[band_name] = band_power
    
    # Prepare data for seaborn
    import pandas as pd
    data_list = []
    for band_name, powers in band_powers.items():
        for p in powers:
            data_list.append({'Band': band_name, 'Power': p * 1e12})  # Convert to pW
    
    df = pd.DataFrame(data_list)
    
    # Create violin plot
    fig, ax = plt.subplots(figsize=(10, 6))
    
    sns.violinplot(
        data=df,
        x='Band',
        y='Power',
        ax=ax,
        palette='husl',
        inner='box'
    )
    
    ax.set_ylabel('Power (pW)', fontsize=12)
    ax.set_xlabel('Frequency Band', fontsize=12)
    ax.set_title('Band Power Distribution Across Channels', fontsize=14)
    
    plt.tight_layout()
    return fig


def plot_topomap(raw: mne.io.Raw, band: tuple = (8, 12)) -> plt.Figure:
    """
    Plot scalp topography for a frequency band.
    
    Args:
        raw: MNE Raw object with montage
        band: (fmin, fmax) tuple
        
    Returns:
        Matplotlib figure
    """
    # Compute PSD
    spectrum = raw.compute_psd(method='welch', fmin=band[0], fmax=band[1], verbose=False)
    psds, freqs = spectrum.get_data(return_freqs=True)
    
    # Average power in band
    band_power = psds.mean(axis=1)
    
    fig, ax = plt.subplots(figsize=(8, 8))
    
    mne.viz.plot_topomap(
        band_power,
        raw.info,
        axes=ax,
        show=False,
        cmap='RdBu_r'
    )
    
    ax.set_title(f'Alpha Power ({band[0]}-{band[1]} Hz)', fontsize=14)
    
    return fig


def plot_confusion_matrix(y_true, y_pred, labels=None) -> plt.Figure:
    """
    Plot confusion matrix.
    
    Args:
        y_true: True labels
        y_pred: Predicted labels
        labels: Label names
        
    Returns:
        Matplotlib figure
    """
    from sklearn.metrics import confusion_matrix
    
    cm = confusion_matrix(y_true, y_pred)
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    sns.heatmap(
        cm,
        annot=True,
        fmt='d',
        cmap='Blues',
        xticklabels=labels or range(cm.shape[0]),
        yticklabels=labels or range(cm.shape[1]),
        ax=ax
    )
    
    ax.set_xlabel('Predicted', fontsize=12)
    ax.set_ylabel('True', fontsize=12)
    ax.set_title('Confusion Matrix', fontsize=14)
    
    plt.tight_layout()
    return fig


def plot_roc_curve(y_true, y_proba, labels=None) -> plt.Figure:
    """
    Plot ROC curve.
    
    Args:
        y_true: True labels
        y_proba: Predicted probabilities
        labels: Class names
        
    Returns:
        Matplotlib figure
    """
    from sklearn.metrics import roc_curve, auc
    
    fig, ax = plt.subplots(figsize=(8, 6))
    
    if len(y_proba.shape) == 1 or y_proba.shape[1] == 2:
        # Binary classification
        if len(y_proba.shape) == 2:
            y_proba = y_proba[:, 1]
        
        fpr, tpr, _ = roc_curve(y_true, y_proba)
        roc_auc = auc(fpr, tpr)
        
        ax.plot(fpr, tpr, lw=2, label=f'ROC (AUC = {roc_auc:.3f})')
    else:
        # Multiclass
        from sklearn.preprocessing import label_binarize
        y_bin = label_binarize(y_true, classes=range(y_proba.shape[1]))
        
        for i in range(y_proba.shape[1]):
            fpr, tpr, _ = roc_curve(y_bin[:, i], y_proba[:, i])
            roc_auc = auc(fpr, tpr)
            label_name = labels[i] if labels else f'Class {i}'
            ax.plot(fpr, tpr, lw=2, label=f'{label_name} (AUC = {roc_auc:.3f})')
    
    ax.plot([0, 1], [0, 1], 'k--', lw=1)
    ax.set_xlim([0.0, 1.0])
    ax.set_ylim([0.0, 1.05])
    ax.set_xlabel('False Positive Rate', fontsize=12)
    ax.set_ylabel('True Positive Rate', fontsize=12)
    ax.set_title('ROC Curve', fontsize=14)
    ax.legend(loc='lower right')
    
    plt.tight_layout()
    return fig


def plot_feature_importance(feature_names, importances, top_n: int = 20) -> plt.Figure:
    """
    Plot feature importance bar chart.
    
    Args:
        feature_names: List of feature names
        importances: Array of importance values
        top_n: Number of top features to show
        
    Returns:
        Matplotlib figure
    """
    import pandas as pd
    
    # Sort by importance
    indices = np.argsort(importances)[::-1][:top_n]
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    df = pd.DataFrame({
        'Feature': [feature_names[i] for i in indices],
        'Importance': importances[indices]
    })
    
    sns.barplot(
        data=df,
        y='Feature',
        x='Importance',
        ax=ax,
        palette='viridis'
    )
    
    ax.set_xlabel('Importance', fontsize=12)
    ax.set_ylabel('Feature', fontsize=12)
    ax.set_title(f'Top {top_n} Feature Importances', fontsize=14)
    
    plt.tight_layout()
    return fig
