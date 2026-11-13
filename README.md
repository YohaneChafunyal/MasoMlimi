
# 🌱 MasoMlimi – Smart Agriculture Platform

MasoMlimi is an AI-powered smart agriculture platform designed to empower farmers across Malawi and Africa through intelligent crop and livestock disease identification, agricultural guidance, and expert communication.

The platform combines artificial intelligence, multilingual support, offline capabilities, and agricultural expertise to make farming knowledge more accessible, especially in rural communities with unreliable internet connectivity.

## 🚀 Key Features

### 📱 Farmer Mobile Application

- **My Farm Dashboard:** Analytics interface for monitoring farm activities and agricultural updates.
- **Weekly Checks:** Green-gradient summary card highlighting scheduled farm checks.
- **Farm Statistics:** Dashboard tiles displaying hosts, alerts, and published guides.
- **Farm Management:** Soft-card layouts for managing farm-related information.
- **Smart Alerts:** Notifications about potential crop and livestock health issues.
- **Recent Activity:** Overview of recent farm interactions and updates.
- **AI-Powered Identification:** Image-based analysis to help identify crop and livestock conditions.
- **Agricultural Guidance:** Recommendations for disease prevention, control, and treatment.
- **Multilingual Support:** English, Chichewa, Swahili, Portuguese, and French.
- **Offline Support:** Enables farmers to access essential features in areas with unreliable connectivity.

### 🧑‍🌾 Agricultural Expert Portal

- Enables agricultural experts to communicate with farmers.
- Provides tools for publishing agricultural guides and recommendations.
- Supports sharing updated farming practices and educational resources.
- Connects farmers with relevant agricultural experts.
- Helps distribute reliable agricultural knowledge to farming communities.

### 🤖 AI-Powered Agricultural Intelligence

- Image-based crop and livestock condition identification.
- AI-assisted agricultural recommendations.
- Multilingual chatbot for interacting with farmers.
- Guidance on disease prevention, control, and treatment.
- Supports better agricultural decision-making.

### 📊 District-Level Agricultural Insights

- Provides insights into frequently reported crop and livestock conditions.
- Helps identify agricultural challenges affecting farming communities.
- Supports targeted agricultural interventions and farmer education.

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| Mobile Application | Flutter / Dart |
| Backend API | Python / FastAPI |
| Expert Portal | HTML, CSS, JavaScript |
| AI Capabilities | Image-based identification |
| API Communication | HTTP / REST |
| Mobile Platform | Android |
| Backend Deployment | Configurable cloud hosting |

## 📁 Project Structure

```text
MasoMlimi/
│
├── backend/
│   ├── app/
│   │   └── main.py
│   └── requirements.txt
│
├── lib/
│   └── Flutter application source
│
├── assets/
│   └── Application assets
│
├── portal/
│   └── Expert portal files
│
└── README.md
```

## ⚙️ Getting Started

### Prerequisites

Ensure you have the following installed:

- Python 3.10+
- Flutter SDK
- Dart SDK
- Android Studio or an Android emulator
- Git

### 1. Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Start the FastAPI server:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Alternatively:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The backend API will be available at:

```text
http://127.0.0.1:8000
```

### 2. Mobile Application Setup

Copy the `lib/` and `assets/` directories into your Flutter project.

Navigate to the Flutter project root and install dependencies:

```bash
flutter pub get
```

Generate application launcher icons:

```bash
dart run flutter_launcher_icons
```

### Run on Android Emulator

```bash
flutter run -d emulator-5554 \
  --dart-define=API_BASE=http://10.0.2.2:8000
```

### Run Using Localhost

```bash
flutter run -d emulator-5554 \
  --dart-define=API_BASE=http://127.0.0.1:8000
```

**Note:** Android emulators use `10.0.2.2` to access the development machine's localhost. The `127.0.0.1` address refers to the emulator itself when running inside the emulator.

### 3. Build Android APK

Generate a release APK:

```bash
flutter build apk --release \
  --dart-define=API_BASE=http://Your-LAN IP:8000
```

Replace `192.168.1.136` with the IP address of the machine hosting your backend.

For production deployment, configure the API base URL to use a secured HTTPS endpoint.

### 4. Expert Portal Setup

Navigate to the portal directory:

```bash
cd portal
```

Start a local HTTP server:

```bash
python -m http.server 5500
```

Open the portal in your browser:

```text
http://127.0.0.1:5500/index.html
```

## 🔒 Safety and Responsible Agricultural Guidance

MasoMlimi prioritises responsible agricultural recommendations and farmer safety.

- Only published and reviewed agricultural procedures should be presented as approved guidance.
- Critical livestock conditions must trigger fixed safety instructions and referral to qualified veterinary professionals.
- AI-generated suggestions should not replace professional agricultural or veterinary diagnosis.
- Farmers should be encouraged to consult qualified experts when conditions are severe or uncertain.
- Agricultural recommendations should be understandable and accessible in supported local languages.

## 🌍 Offline-First Approach

Recognising that internet connectivity is unreliable in many African rural communities, MasoMlimi incorporates offline functionality into the farmer-facing application.

This approach aims to:

- Allow farmers to access essential application features without continuous internet connectivity.
- Support local access to available agricultural information.
- Synchronise data when internet connectivity becomes available.
- Make agricultural technology more accessible to underserved farming communities.

## 📈 Development Status

MasoMlimi is currently under active development.

Ongoing development areas include:

- Farmer mobile application.
- Backend API services.
- AI-powered crop and livestock identification.
- Multilingual agricultural chatbot.
- Agricultural expert portal.
- Offline data management and synchronisation.
- Agricultural analytics and district-level insights.

## 🎯 Project Vision

To empower farmers across Malawi and Africa with accessible, multilingual, AI-powered agricultural tools that improve farming decisions, strengthen agricultural knowledge sharing, and support more resilient farming communities.

## 🤝 Contributing

Contributions, technical feedback, partnerships, and agricultural expertise are welcome.

Developers, agricultural researchers, institutions, and organisations interested in advancing digital agriculture are encouraged to collaborate.


**MasoMlimi – Empowering Farmers Through Technology. 🌱**
