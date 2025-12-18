<h1 align="center">BioGPT-DDI</h1>

<p align="center">
  <b>Biomedical GPT for Drug–Drug Interaction Prediction and Explainable Clinical Reports</b>
</p>

<p align="center">
  A biomedical AI system that leverages BioGPT to predict drug–drug interactions
  and generate clinically meaningful, explainable summaries.
</p>

---

## 🔬 Project Overview

**BioGPT-DDI** is a biomedical natural language processing (NLP) project that applies a  
**domain-specific large language model (BioGPT)** to the task of **drug–drug interaction (DDI) prediction**.

Drug–drug interactions are a major cause of adverse drug reactions and clinical complications.
Most existing systems rely on static databases and predefined rules, which limits their ability
to adapt to new findings in biomedical literature.

This project demonstrates how **biomedical language models** can be used to:
- understand pharmacological context
- reason about drug relationships
- generate human-readable clinical explanations

---

## 🧠 What This Project Does

BioGPT-DDI focuses on two core capabilities:

### 🔹 Drug–Drug Interaction Prediction
Given two drug names, the system predicts whether an interaction exists and estimates
the severity of the interaction using BioGPT’s biomedical language understanding.

### 🔹 Explainable Clinical Report Generation
Instead of returning only a label, the system generates a **natural-language explanation**
describing the interaction, associated risks, and clinical implications.

This improves interpretability and makes the output more useful for real-world biomedical scenarios.

---

## 🧬 Why BioGPT?

**BioGPT** is a transformer-based language model trained specifically on large-scale
biomedical literature. Compared to general-purpose language models, BioGPT is better at:

- understanding biomedical terminology
- capturing pharmacological relationships
- generating clinically coherent text

Using a domain-trained model significantly improves the quality of both predictions
and explanations in healthcare-related tasks.

---

## 🏗️ Current Architecture

This version of the project is implemented as a **simple web-based system**, focusing on
model integration and explainability rather than distributed or cloud infrastructure.

- **Frontend**  
  A web interface for entering drug names and viewing predictions.

- **Backend API**  
  Handles inference requests and communicates with the BioGPT model.

- **Language Model**  
  BioGPT is used for both interaction prediction and explanation generation.

---

## 📁 Project Structure

- **api/**  
  Backend logic for handling requests, running the BioGPT model,
  and returning predictions and explanations.

- **src/**  
  Frontend source code including UI components and application pages.

- **public/**  
  Static assets such as images or icons.

- **package.json**  
  Project dependencies and scripts.

- **vercel.json**  
  Deployment configuration for hosting the application.

---

## ⚙️ How the System Works

1. The user enters two drug names through the web interface.  
2. The frontend sends the drug pair to the backend API.  
3. The backend processes the input using the BioGPT model.  
4. The model predicts a possible interaction and generates an explanation.  
5. The result is returned and displayed on the user interface.

---

## 🧪 Example

**Input**
- Drug 1: Aspirin  
- Drug 2: Warfarin  

**Output**
- **Interaction:** Severe  
- **Explanation:**  
  Aspirin may enhance the anticoagulant effect of Warfarin, increasing the risk of
  bleeding and related complications.

---

## 🎯 Use Cases

- Academic and major projects in biomedical AI  
- Biomedical NLP experimentation  
- Learning how large language models can be applied to healthcare  
- Prototyping early clinical decision-support systems  

---

## 🔮 Future Improvements

- Support for additional drug datasets  
- Improved explanation formatting and readability  
- Interaction confidence scoring  
- Multi-drug interaction analysis  
- UI/UX enhancements  

---

## 📄 License

This project is licensed under the **MIT License**.

---

## 🙌 Acknowledgements

- **BioGPT** by Microsoft Research  
- Biomedical datasets such as DrugBank and TWOSIDES  
- Open-source NLP and AI research community
