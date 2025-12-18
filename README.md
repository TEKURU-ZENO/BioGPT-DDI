# BioGPT-DDI  
### Biomedical GPT for Drug–Drug Interaction Prediction & Explainable Clinical Reports

BioGPT-DDI is a web-based biomedical AI application that predicts **drug–drug interactions (DDIs)** and generates **explainable clinical reports** using a fine-tuned **BioGPT** model.  
The project focuses on applying large language models to real-world healthcare problems through a simple frontend–backend architecture.

---

## 🚀 Features

- 🔍 Predicts whether two drugs interact
- ⚠️ Classifies interaction severity
- 🧠 Uses BioGPT for biomedical text understanding
- 📝 Generates explainable, human-readable clinical summaries
- 💻 Web-based interface for easy interaction
- ⚡ Lightweight backend API for inference

---

## 📁 Project Structure

BioGPT-DDI/
│
├── api/ # Backend API (prediction & report generation)
│ ├── index.js # Main API handler
│ └── ... # Supporting logic
│
├── public/ # Static assets
│ └── ...
│
├── src/ # Frontend source code
│ ├── components/ # UI components
│ ├── pages/ # Application pages
│ ├── App.js # Root component
│ └── index.js # Entry point
│
├── package.json # Dependencies & scripts
├── vercel.json # Deployment configuration
├── LICENSE
└── README.md

yaml
Copy code

---

## 🧠 Project Overview

Drug–drug interactions are a major cause of adverse drug reactions and medical errors.  
Most existing systems rely on static databases that do not adapt well to new findings in biomedical literature.

BioGPT-DDI addresses this problem by:
- Leveraging **BioGPT**, a transformer model trained on biomedical text
- Automatically predicting interactions between drug pairs
- Generating clear, explainable summaries to help users understand the interaction

---

## 🧰 Tech Stack

| Layer | Technology |
|------|------------|
| Frontend | JavaScript (React-based UI) |
| Backend | Node.js API |
| Language Model | BioGPT |
| Deployment | Vercel |
| Language | JavaScript |

---

## 🔧 Installation & Setup

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/TEKURU-ZENO/BioGPT-DDI.git
cd BioGPT-DDI
2️⃣ Install Dependencies
bash
Copy code
npm install
3️⃣ Run the Application
bash
Copy code
npm run dev
4️⃣ Open in Browser
arduino
Copy code
http://localhost:3000
⚙️ How It Works
User Input
The user enters two drug names through the web interface.

API Request
The frontend sends the drug pair to the backend API.

BioGPT Inference
The backend processes the input using the BioGPT model to:

Detect possible interaction

Generate an explainable report

Result Display
The interaction prediction and explanation are shown on the UI.

🧪 Example
Input

less
Copy code
Drug A: Aspirin  
Drug B: Warfarin
Output

Interaction: Severe

Explanation:

nginx
Copy code
Aspirin may increase the anticoagulant effect of Warfarin, increasing the risk of bleeding...
📌 Use Cases
Academic projects in AI & healthcare

Biomedical NLP experimentation

Learning how LLMs can be applied to clinical decision support

Prototype for future healthcare AI systems

🔮 Future Improvements
Add support for more drug databases

Improve UI/UX and result visualization

Add confidence scores and risk levels

Support multi-drug interaction analysis

Extend to multi-language explanations

📄 License
This project is licensed under the MIT License.

🙌 Acknowledgements
BioGPT by Microsoft Research

Biomedical datasets such as DrugBank and TWOSIDES

Open-source NLP and ML communities

📬 Contact
For questions or suggestions, feel free to reach out or open an issue in the repository.
