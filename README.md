<div align="center">

# 🧠 NeuroLab

**A Modern Platform for Neural Signal Processing & Machine Learning**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![MNE](https://img.shields.io/badge/MNE--Python-1.6-blue?style=for-the-badge)](https://mne.tools)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

*Automate the processing, feature extraction, and classification of EEG/MEG neural time-series data*

[Features](#-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [API Reference](#-api-reference) • [Contributing](#-contributing)

</div>

<p align="center">
  <img src="github.com/Atiyakh/NeuroLab/blob/main/screenshots/Screenshot%202026-02-03%20053607.png?raw=true">
</p>

<p align="center">
  <img src="github.com/Atiyakh/NeuroLab/blob/main/screenshots/Screenshot%202026-02-03%20053541.png?raw=true">
</p>

---

> **Note:** I have some reservations about making the repository public at this stage, as the project is still in a very early phase of development.

## ✨ Features

<table>
<tr>
<td width="50%">

### 📥 Data Ingestion
- Upload **EDF**, **BDF**, **FIF**, and **SET** files
- Automatic metadata extraction
- BIDS-compatible organization
- Batch upload support

</td>
<td width="50%">

### ⚡ Preprocessing Pipeline
- Resampling to target frequency
- Notch filtering (50/60 Hz)
- Bandpass filtering (configurable)
- Bad channel detection & interpolation
- ICA-based artifact removal

</td>
</tr>
<tr>
<td width="50%">

### 📊 Feature Extraction
- **Band Power**: Delta, Theta, Alpha, Beta, Gamma
- **Time Domain**: Mean, variance, skewness, kurtosis
- **Hjorth Parameters**: Activity, mobility, complexity
- **Entropy**: Sample entropy, spectral entropy
- **Connectivity**: Coherence, phase-locking value

</td>
<td width="50%">

### 🤖 Machine Learning
- Random Forest, SVM, Logistic Regression
- Gradient Boosting classifiers
- Cross-validation & hyperparameter tuning
- Model versioning & deployment
- ROC curves & confusion matrices

</td>
</tr>
<tr>
<td width="50%">

### 📡 Real-time Processing
- WebSocket-based streaming
- Live feature computation
- Real-time inference
- Band power visualization

</td>
<td width="50%">

### 📈 Visualizations
- PSD heatmaps
- Topographic maps
- Raw signal traces
- Training metrics & curves

</td>
</tr>
</table>

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- (Optional) Docker & Docker Compose

### Local Development

**1. Clone the repository**
```bash
git clone https://github.com/Atiyakh/NeuroLab.git
cd NeuroLab
```

**2. Set up the backend**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
python run.py
```

**3. Set up the frontend**
```bash
cd frontend
npm install
npm start
```

**4. Open in browser**
```
http://localhost:3000
```

### Docker Deployment

```bash
docker-compose up -d
```

This starts:
- 🌐 Frontend (React) on port `3000`
- 🔧 Backend (Flask) on port `5000`
- 🗄️ PostgreSQL on port `5432`
- 📦 Redis on port `6379`
- 💾 MinIO on port `9000`

---

## 🏗️ Architecture

```mermaid
flowchart LR
    %% Frontend & API
    React[React SPA\nPort 3000]
    Flask[Flask API\nPort 5000]
    Postgres[(PostgreSQL\nMetadata)]

    React <-->|HTTP| Flask
    Flask <-->|SQL| Postgres

    %% Async & Storage Layer
    Redis[(Redis\nBroker)]
    Celery[Celery\nWorkers]
    MinIO[(MinIO\nS3 Files)]

    Flask <-->|WebSocket / Task Queue| Redis
    Redis <-->|Tasks| Celery
    Celery <-->|Jobs| MinIO
    Redis <-->|Jobs| MinIO

```

### Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, Recharts, Socket.IO Client, React Dropzone |
| **Backend** | Flask 3.0, Flask-SocketIO, Flask-JWT-Extended |
| **Processing** | MNE-Python 1.6, NumPy, SciPy, Pandas |
| **ML** | scikit-learn 1.3, joblib |
| **Database** | PostgreSQL (prod) / SQLite (dev) |
| **Queue** | Celery 5.3 + Redis |
| **Storage** | MinIO (S3-compatible) |
| **Deployment** | Docker, Docker Compose |

---

## 📁 Project Structure

```
NeuroLab/
├── backend/
│   ├── app/
│   │   ├── api/              # REST API endpoints
│   │   │   ├── auth.py       # Authentication
│   │   │   ├── ingest.py     # File upload
│   │   │   ├── recordings.py # Recording management
│   │   │   ├── models.py     # ML model endpoints
│   │   │   └── dashboard.py  # Statistics
│   │   ├── processing/       # Signal processing
│   │   │   ├── preprocessing.py
│   │   │   ├── features.py
│   │   │   └── visualization.py
│   │   ├── tasks/            # Celery background tasks
│   │   ├── services/         # Storage service
│   │   ├── models.py         # Database models
│   │   └── config.py         # Configuration
│   ├── tests/                # Unit tests
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── pages/            # React pages
│   │   │   ├── Dashboard.js
│   │   │   ├── Upload.js
│   │   │   ├── Recordings.js
│   │   │   ├── RecordingView.js
│   │   │   ├── Models.js
│   │   │   └── RealtimeDashboard.js
│   │   ├── services/         # API & WebSocket
│   │   ├── context/          # Auth context
│   │   └── index.css         # Styles
│   └── package.json
├── docker-compose.yml
└── README.md
```

---

## 📡 API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/register` | Create new user |
| `POST` | `/api/login` | Get access token |
| `POST` | `/api/refresh` | Refresh token |

### Recordings

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/ingest` | Upload recording file |
| `GET` | `/api/recordings` | List all recordings |
| `GET` | `/api/recordings/:id` | Get recording details |
| `POST` | `/api/recordings/:id/start_preprocess` | Start preprocessing |
| `POST` | `/api/recordings/:id/extract_features` | Extract features |

### Models

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/models` | List all models |
| `POST` | `/api/models/train` | Train new model |
| `POST` | `/api/models/:id/promote` | Promote to production |
| `POST` | `/api/predict` | Run inference |

---

## ⚙️ Configuration

Create a `.env` file based on `.env.example`:

```env
# Flask
SECRET_KEY=your-secret-key
FLASK_DEBUG=true

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/neurolab

# Redis
REDIS_URL=redis://localhost:6379/0

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# JWT
JWT_SECRET_KEY=your-jwt-secret
```

### Processing Parameters

Customize in `backend/app/config.py`:

```python
PROCESSING_CONFIG = {
    'target_sfreq': 250,           # Target sampling rate
    'notch_freqs': [50],           # Line noise (50 Hz EU, 60 Hz US)
    'bandpass': {'low': 1.0, 'high': 40.0},
    'ica': {
        'n_components': 20,
        'method': 'fastica'
    },
    'features': {
        'bands': [
            {'name': 'delta', 'low': 1, 'high': 4},
            {'name': 'theta', 'low': 4, 'high': 8},
            {'name': 'alpha', 'low': 8, 'high': 12},
            {'name': 'beta', 'low': 12, 'high': 30},
            {'name': 'gamma', 'low': 30, 'high': 45}
        ]
    }
}
```

---

## 🧪 Testing

```bash
cd backend
pytest tests/ -v --cov=app
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built with ❤️ for the neuroscience community**

[⬆ Back to Top](#-neurolab)

</div>
